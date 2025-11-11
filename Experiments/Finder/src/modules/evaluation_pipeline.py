import os
import sys
import subprocess as sp
import pandas as pd
import shutil
import json
import re
import argparse
import numpy as np
import copy
import math
import random
from tqdm import tqdm

class EvaluationPipeline:
    def __init__(
            self,
            project_fixed_methods,
            class_locs_path,
            func_locs_path,
            project_source_code_dir,
            external_apis_csv_path = None,
            candidate_apis_csv_path = None,
            llm_labelled_sink_apis_path = None,
            llm_labelled_source_apis_path = None,
            llm_labelled_taint_prop_apis_path = None,
            source_func_param_candidates_path = None,
            llm_labelled_source_func_params_path = None,
            query_output_result_sarif_path = None,
            posthoc_filtering_output_result_sarif_path = None,
            final_output_json_path = None,
            project_logger = None,
            overwrite = False,
            test_run = False,
    ):
        self.project_fixed_methods = project_fixed_methods
        self.class_locs_path = class_locs_path
        self.func_locs_path = func_locs_path
        self.project_source_code_dir = project_source_code_dir
        self.external_apis_csv_path = external_apis_csv_path
        self.candidate_apis_csv_path = candidate_apis_csv_path
        self.llm_labelled_sink_apis_path = llm_labelled_sink_apis_path
        self.llm_labelled_source_apis_path = llm_labelled_source_apis_path
        self.llm_labelled_taint_prop_apis_path = llm_labelled_taint_prop_apis_path
        self.source_func_param_candidates_path = source_func_param_candidates_path
        self.llm_labelled_source_func_params_path = llm_labelled_source_func_params_path
        self.query_output_result_sarif_path = query_output_result_sarif_path
        self.posthoc_filtering_output_result_sarif_path = posthoc_filtering_output_result_sarif_path
        self.final_output_json_path = final_output_json_path
        self.project_logger = project_logger
        self.overwrite = overwrite,
        self.test_run = test_run

    def get_source_line(self, location):
        relative_file_url = location["location"]["physicalLocation"]["artifactLocation"]["uri"]
        line_num = location["location"]["physicalLocation"]["region"]["startLine"]
        file_dir = f"{self.project_source_code_dir}/{relative_file_url}"
        if not os.path.exists(file_dir):
            print("Not found ", file_dir)
            return ""
        else:
            file_lines = list(open(file_dir, 'r').readlines())
            if line_num > len(file_lines):
                return ""
            else:
                line = file_lines[line_num - 1]
                return line

    def compute_statistics(self):
        if self.test_run:
            num_external_api_calls = 0
            num_api_candidates = 0
            num_labelled_sinks = 0
            num_labelled_sources = 0
            num_labelled_taint_props = 0
            num_func_param_candidates = 0
            num_labelled_func_param_sources = 0
        else:
            num_external_api_calls = len(pd.read_csv(self.external_apis_csv_path))
            num_api_candidates = len(pd.read_csv(self.candidate_apis_csv_path))
            num_labelled_sinks = len(json.load(open(self.llm_labelled_sink_apis_path)))
            num_labelled_sources = len(json.load(open(self.llm_labelled_source_apis_path)))
            num_labelled_taint_props = len(json.load(open(self.llm_labelled_taint_prop_apis_path)))
            num_func_param_candidates = len(pd.read_csv(self.source_func_param_candidates_path))
            num_labelled_func_param_sources = len(json.load(open(self.llm_labelled_source_func_params_path)))

        return {
            "num_external_api_calls": num_external_api_calls,
            "num_api_candidates": num_api_candidates,
            "num_labelled_sources": num_labelled_sources,
            "num_labelled_taint_propagators": num_labelled_taint_props,
            "num_labelled_sinks": num_labelled_sinks,
            "num_public_func_candidates": num_func_param_candidates,
            "num_labelled_func_param_sources": num_labelled_func_param_sources,
            "num_gpt_calls_for_posthoc_filtering": 0,
            "num_cached_during_posthoc_filtering": 0,
        }

    def extract_code_flow_passing_files(self, code_flow):
        thread_flow = code_flow["threadFlows"][0]
        locations = thread_flow["locations"]
        for loc in locations:
            file_name = loc["location"]["physicalLocation"]["artifactLocation"]["uri"]
            yield file_name

    def extract_code_flow_passing_methods(self, project_classes, project_methods, code_flow):
        thread_flow = code_flow["threadFlows"][0]
        locations = thread_flow["locations"]
        for loc in locations:
            try:
                file_name = loc["location"]["physicalLocation"]["artifactLocation"]["uri"]
                region = loc["location"]["physicalLocation"]["region"]
                start_line = region["startLine"]

                # Get the closest enclosing class
                relevant_classes = project_classes[
                    (project_classes["file"] == file_name) &
                    (project_classes["start_line"] <= start_line) &
                    (project_classes["end_line"] >= start_line)
                ].sort_values(by="start_line", ascending=False)
                if len(relevant_classes) == 0: continue
                relevant_class = relevant_classes.iloc[0]["name"]

                # Get the closest enclosing method
                relevant_methods = project_methods[
                    (project_methods["file"] == file_name) &
                    (project_methods["start_line"] <= start_line) &
                    (project_methods["end_line"] >= start_line)
                ].sort_values(by="start_line", ascending=False)
                if len(relevant_methods) == 0: continue
                relevant_method = relevant_methods.iloc[0]["name"]
            except Exception as e:
                continue
            # Yield
            yield f"{file_name}:{relevant_class}:{relevant_method}"

    def iter_code_flows(self, sarif_json):
        """
        Iterate through the code flows within a SARIF json obtained from running path queries with CodeQL
        """
        for (i, result) in enumerate(sarif_json["runs"][0]["results"]):
            if "codeFlows" not in result: continue
            code_flows = result["codeFlows"]
            for (j, code_flow) in enumerate(code_flows):
                yield (i, j, code_flow)

    def ignore_code_flow(self, code_flow):
        thread_flow = code_flow["threadFlows"][0]
        locations = thread_flow["locations"]
        first_location = locations[0]
        last_location = locations[-1]

        # {
        #   'location': {
        #     'physicalLocation': {
        #       'artifactLocation': {
        #         'uri': 'dspace-api/src/main/java/org/dspace/administer/CommunityFiliator.java',
        #         'uriBaseId': '%SRCROOT%',
        #         'index': 0
        #       },
        #       'region': {
        #         'startLine': 81,
        #         'startColumn': 24,
        #         'endColumn': 48
        #       }
        #     },
        #     'message': {
        #       'text': 'getOptionValue(...) : String'
        #     }
        #   }
        # }

        def is_println(loc):
            # line = self.get_source_line(loc)
            # if ".println(" in line or ".print(" in line: return True
            return False

        def ignore_location(loc):
            if "toString" in loc['location']['message']['text']: return True
            if "println" in loc['location']['message']['text']: return True
            # if "... + ..." in loc['location']['message']['text']: return True
            # if "next(" in loc['location']['message']['text']: return True
            # if "getOptionValue(" in loc['location']['message']['text']: return True
            # if "get(" in loc['location']['message']['text']: return True
            # if "getProperty(" in loc['location']['message']['text']: return True
            return False

        ignore = is_println(last_location)
        if not ignore: ignore = ignore or ignore_location(first_location)
        if not ignore: ignore = ignore or ignore_location(last_location)
        return ignore

    def evaluate_sarif_result(self, sarif_path):
        if self.test_run: return {}

        # 1. Load the SARIF file
        result_sarif = json.load(open(sarif_path))

        # 2. Extract function and class locations
        project_classes = pd.read_csv(self.class_locs_path)
        project_methods = pd.read_csv(self.func_locs_path)

        # 3. Compute the fixed locations
        fixed_files, fixed_methods = set(), set()
        for (_, row) in self.project_fixed_methods.iterrows():
            file_name, class_name, method_name = row["file"], row["class"], row["method"]
            if "src/test" in file_name: continue
            fixed_files.add(file_name)
            fixed_methods.add(f"{file_name}:{class_name}:{method_name}")

        # 4. Iterate through all the code flows, and check if the passing locations has intersection with fixed locations
        code_flow_passes_fix_file, code_flow_passes_fix_method = False, False
        num_true_pos_paths_file, num_true_pos_paths_method = 0, 0
        tp_result_file_ids, tp_result_method_ids = set(), set()
        num_total = 0
        all_code_flows = self.iter_code_flows(result_sarif)
        code_flow_iterator = tqdm(list(all_code_flows))
        for (result_id, _, code_flow) in code_flow_iterator:
            # 4.0. Filter code flows
            if self.ignore_code_flow(code_flow):
                continue

            # 4.1. Get recall@file
            passing_files = set(self.extract_code_flow_passing_files(code_flow))
            if len(fixed_files.intersection(passing_files)) > 0:
                code_flow_passes_fix_file = True
                num_true_pos_paths_file += 1
                tp_result_file_ids.add(result_id)

            # 4.1. Get recall@method
            passing_methods = set(self.extract_code_flow_passing_methods(project_classes, project_methods, code_flow))
            if len(fixed_methods.intersection(passing_methods)) > 0:
                code_flow_passes_fix_method = True
                num_true_pos_paths_method += 1
                tp_result_method_ids.add(result_id)

            num_total += 1

        num_true_pos_results_file, num_true_pos_results_method = len(tp_result_file_ids), len(tp_result_method_ids)

        # 5. Return
        return {
            "num_results": len(result_sarif["runs"][0]["results"]),
            "num_paths": num_total,
            "recall_file": code_flow_passes_fix_file,
            "num_tp_paths_file": num_true_pos_paths_file,
            "num_tp_results_file": num_true_pos_results_file,
            "recall_method": code_flow_passes_fix_method,
            "num_tp_paths_method": num_true_pos_paths_method,
            "num_tp_results_method": num_true_pos_results_method,
        }

    def run_vanilla_only(self):
        if os.path.exists(self.final_output_json_path) and not self.overwrite:
            result = json.load(open(self.final_output_json_path))
            if self.project_logger is not None:
                # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {result['recall_file']}, #Paths: {result['num_paths']}, #TP: {result['num_tp_paths_file']}")
                self.project_logger.info(f"    ==> [Recall@Method] RESULT: {result['recall_method']}, #Paths: {result['num_paths']}, #TP: {result['num_tp_paths_method']}")
        elif os.path.exists(self.query_output_result_sarif_path):
            result = self.evaluate_sarif_result(self.query_output_result_sarif_path)
            if self.project_logger is not None:
                # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {result['recall_file']}, #Paths: {result['num_paths']}, #TP: {result['num_tp_paths_file']}")
                self.project_logger.info(f"    ==> [Recall@Method] RESULT: {result['recall_method']}, #Paths: {result['num_paths']}, #TP: {result['num_tp_paths_method']}")
            json.dump(result, open(self.final_output_json_path, "w"))
        else:
            self.project_logger.info("    ==> Vanilla result file not found...")

    def run(self):
        need_eval = True
        if os.path.exists(self.final_output_json_path) and not self.overwrite:
            need_eval = False
            self.project_logger.info("  ==> Found existing statistics, loading...")
            result = json.load(open(self.final_output_json_path))
            if "vanilla_result" not in result:
                need_eval = True
            if "posthoc_filter_result" not in result:
                need_eval = True

        if need_eval:
            result = {}

            self.project_logger.info("  ==> Computing statistics...")
            result.update({ "statistics": self.compute_statistics() })

            self.project_logger.info("  ==> Evaluating results after stage 6 (vanilla)...")
            if os.path.exists(self.query_output_result_sarif_path):
                vanilla_result = self.evaluate_sarif_result(self.query_output_result_sarif_path)

                if self.project_logger is not None:
                    # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {vanilla_result['recall_file']}, #Paths: {vanilla_result['num_paths']}, #TP Paths: {vanilla_result['num_tp_paths_file']}")
                    self.project_logger.info(f"    ==> [Recall@Method] RESULT: {vanilla_result['recall_method']}, #Paths: {vanilla_result['num_paths']}, #TP Paths: {vanilla_result['num_tp_paths_method']}")

                result.update({ "vanilla_result": vanilla_result })
            else:
                self.project_logger.info("    ==> Vanilla result file not found...")

            self.project_logger.info("  ==> Evaluating results after stage 7 (with posthoc-filtering)...")
            if os.path.exists(self.posthoc_filtering_output_result_sarif_path):
                posthoc_result = self.evaluate_sarif_result(self.posthoc_filtering_output_result_sarif_path)

                if self.project_logger is not None:
                    # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {posthoc_result['recall_file']}, #Paths: {posthoc_result['num_paths']}, #TP Paths: {posthoc_result['num_tp_paths_file']}")
                    self.project_logger.info(f"    ==> [Recall@Method] RESULT: {posthoc_result['recall_method']}, #Paths: {posthoc_result['num_paths']}, #TP Paths: {posthoc_result['num_tp_paths_method']}")

                result.update({ "posthoc_filter_result": posthoc_result })
            else:
                self.project_logger.info("    ==> Posthoc filtering result file not found...")

            self.project_logger.info(f"  ==> Dumping final statistics and evaluation result to {'/'.join(self.final_output_json_path.split('/')[-4:])}...")
            json.dump(result, open(self.final_output_json_path, "w"))
        else:
            if "vanilla_result" in result:
                self.project_logger.info("  ==> Evaluating results after stage 6 (vanilla)...")
                # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {result['vanilla_result']['recall_file']}, #Paths: {result['vanilla_result']['num_paths']}, #TP Paths: {result['vanilla_result']['num_tp_paths_file']}")
                self.project_logger.info(f"    ==> [Recall@Method] RESULT: {result['vanilla_result']['recall_method']}, #Paths: {result['vanilla_result']['num_paths']}, #TP Paths: {result['vanilla_result']['num_tp_paths_method']}")
            if "posthoc_filter_result" in result:
                self.project_logger.info("  ==> Evaluating results after stage 7 (with posthoc-filtering)...")
                # self.project_logger.info(f"    ==> [Recall@File]   RESULT: {result['posthoc_filter_result']['recall_file']}, #Paths: {result['posthoc_filter_result']['num_paths']}, #TP Paths: {result['posthoc_filter_result']['num_tp_paths_file']}")
                self.project_logger.info(f"    ==> [Recall@Method] RESULT: {result['posthoc_filter_result']['recall_method']}, #Paths: {result['posthoc_filter_result']['num_paths']}, #TP Paths: {result['posthoc_filter_result']['num_tp_paths_method']}")
