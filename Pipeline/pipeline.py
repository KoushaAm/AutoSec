from typing import TypedDict, Dict, Any, Optional
import logging
import uuid
import argparse
import json
from langgraph.graph import StateGraph, END

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autossec.langgraph")

# this implementation doesn't not do any retries

class AutoSecState(TypedDict, total=False):
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    artifacts: Optional[Dict[str, str]]
    exploiter: Optional[Dict[str, Any]]
    patcher: Optional[Dict[str, Any]]
    verifier: Optional[Dict[str, Any]]    

def build_workflow() -> Any:
    graph = StateGraph(AutoSecState)
    graph.add_node("finder", finder_node)
    graph.add_node("exploiter", exploiter_node)
    graph.add_node("patcher", patcher_node)
    graph.add_node("verifier", verifier_node)

    # linear edges
    graph.add_edge("finder", "exploiter")
    graph.add_edge("exploiter", "patcher")
    graph.add_edge("patcher", "verifier")
    graph.add_edge("verifier", END)

    workflow = graph.compile()
    return workflow


def get_db() -> dict:
    # function to pull vulnerabilties from database
    return [] # returns json object

def push_db() -> tuple[int, str]:
    # function to push vulnerabilities into the database
    return (400, "Failed")



def finder_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: finder started")
    # implementation
    return state


def exploiter_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: exploiter started")
    return state


def patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: patcher started")
    return state


def verifier_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: verifier started")
    return state