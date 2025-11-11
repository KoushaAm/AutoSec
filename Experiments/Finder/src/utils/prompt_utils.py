from data.prompt import PROMPTS, PROMPTS_SYSTEM
import pandas as pd
import os

cwenames = pd.read_csv("utils/cwenames_top25.txt", index_col="id")

def get_cwe_name_from_id(id):
    if int(id) == -1:
        return "any vulnerability"
    return f"CWE-{str(id)} ({cwenames.loc[int(id)]['name']})"

def generate_message_list(prompting_technique, snippet, prompt_cwe=-1, user_prompt="generic", system_prompt="generic"):
    if "self_reflection" in prompting_technique:
        prompt_message_list = generate_self_reflection_message_list(
            snippet=snippet, prompt_cwe=prompt_cwe
        )
    elif "instruction_cot" in prompting_technique:
        prompt_message_list = generate_system_heuristics_cot_message_list(
            snippet=snippet, prompt_cwe=prompt_cwe, validate=True
        )
    elif "step_by_step_dataflow_analysis" in prompting_technique:
        prompt_message_list = generate_step_by_step_dataflow_analysis_message_list(
            snippet=snippet, prompt_cwe=prompt_cwe, system_prompt_type=None
        )
    elif prompting_technique == "few_shot_cot":
        prompt_message_list = generate_few_shot_cot_message_list(
            snippet=snippet, prompt_cwe=prompt_cwe
        )
    elif "basic" in prompting_technique:
        prompt_message_list = generate_basic_message_list(
            snippet=snippet,
            prompt_cwe=prompt_cwe,
            prompt_type=user_prompt,
            system_prompt_type=system_prompt
        )
    else:
        raise Exception(f"Prompting technique: {prompting_technique} not found")
    return prompt_message_list

def generate_basic_message_list(snippet, prompt_cwe, prompt_type, system_prompt_type, validate=False):
    """
    Generate an OpenAI API-style message with a system and a user prompt
    """
    query = PROMPTS[prompt_type].format(snippet, get_cwe_name_from_id(prompt_cwe))
    system_prompt = PROMPTS_SYSTEM[system_prompt_type]
    message_list = [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}]
    if validate:
        message_list.append({
            "role": "user",
            "content": "Is this analysis correct?"
        })

    return message_list

def generate_self_reflection_message_list(snippet, prompt_cwe=-1):
    """
    Generate an OpenAI API-stye message list with self reflection messages
    """
    return [
        {
            "role": "user",
            "content": PROMPTS["taint_analysis"].format(snippet)
        },
        {
            "role": "user",
            "content": "Is this analysis correct?"
        },
        {
            "role": "user",
            "content": f"Based on this analysis, is the given code snippet prone to {get_cwe_name_from_id(prompt_cwe)}? Provide response only in following format: '$$ vulnerability: <YES or NO> | vulnerability type: <CWE_ID> | lines of code: <VULNERABLE_LINES_OF_CODE> | explanation: <explanation for prediction> $$'."
        }
    ]

def generate_system_heuristics_cot_message_list(snippet, prompt_cwe=-1, validate=False):
    """
    Generate an OpenAI API-stye message list with well_crafted system prompt + cot messages
    Add a self reflection style prompt if validate = True
    """
    messages = [
        {
            "role": "system",
            "content": PROMPTS_SYSTEM["heuristics"]
        },
        {
            "role": "user",
            "content": PROMPTS["zero_shot_cot"].format(snippet, get_cwe_name_from_id(prompt_cwe))
        }
    ]
    if validate:
        messages.append(
            {
                "role": "user",
                "content": "Is this analysis correct?"
            }
        )
    messages.append({
        {
            "role": "user",
            "content": f"Based on this analysis, is the given code snippet prone to {get_cwe_name_from_id(prompt_cwe)}? Provide response only in following format: '$$ vulnerability: <YES or NO> | vulnerability type: <CWE_ID> | lines of code: <VULNERABLE_LINES_OF_CODE> | explanation: <explanation for prediction> $$'."
        }
    })
    return messages

def generate_few_shot_cot_message_list(snippet, prompt_cwe=-1, system_prompt_type=None):
    """
    Generate an OpenAI API-stye message list with few shot messages
    Add a self reflection style prompt if validate = True
    """
    messages = []
    if system_prompt_type:
        messages.append({
            "role": "system",
            "content": PROMPTS_SYSTEM[system_prompt_type]
        })
    messages.append({
        "role": "user",
        "content": PROMPTS["cpp_few_shot"].format(snippet)
    })
    return messages

def generate_step_by_step_dataflow_analysis_message_list(snippet, prompt_cwe=-1, system_prompt_type=None):
    """
    Generate an OpenAI API-stye message list with few shot messages
    Add a self reflection style prompt if validate = True
    """
    messages = []
    if system_prompt_type:
        messages.append({
            "role": "system",
            "content": PROMPTS_SYSTEM[system_prompt_type]
        })
    messages.extend([
        {
            "role": "user",
            "content": PROMPTS["identify_sources_sinks_sanitizers"].format(snippet)
        },
        {
            "role": "user",
            "content": "Now find the flows between these identified sources and sinks that are not sanitized."
        },
        {
            "role": "user",
            "content": f"Based on this analysis, is the given code snippet prone to {get_cwe_name_from_id(prompt_cwe)}? Provide response only in following format: '$$ vulnerability: <YES or NO> | vulnerability type: <CWE_ID> | lines of code: <VULNERABLE_LINES_OF_CODE> | explanation: <explanation for prediction> $$'."
        }
    ])
    return messages

def generate_validation_message_list(id, dataset_results_dir):
    existing_results_dir = os.path.join(dataset_results_dir, id)
    prompt_log = open(os.path.join(existing_results_dir, "query.txt")).read().strip()
    pred = open(os.path.join(existing_results_dir, "pred.txt")).read().strip()

    prompt_sep = "-------------------"
    prompts = prompt_log.split(prompt_sep)
    # Each prompt of the format
    # ROLE
    #
    # <CONTENT>
    # for prompt in prompts:
    #     print(prompt)
    #     print("+++++++++++++++=")
    messages = [
        {
            "role": prompt.strip().splitlines()[0].lower(), 
            "content": "\n".join(prompt.strip().splitlines()[2:])
        } for prompt in prompts if len(prompt.strip()) > 0]
    
    # Add the validation prompt
    messages.extend([
        {"role": "assistant", "content": pred},
        {"role": "user", "content": PROMPTS["validation"]}])
    return messages



