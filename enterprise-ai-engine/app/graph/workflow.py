from langgraph.graph import StateGraph, END
from .nodes import classify_node, process_node, decision_node , validation_node , risk_node
from .state import WorkflowState

graph = StateGraph(WorkflowState)

graph.add_node("classifier", classify_node)
graph.add_node("processor", process_node)
graph.add_node("decision", decision_node)
graph.add_node("validation", validation_node)
graph.add_node("risk", risk_node)

graph.set_entry_point("classifier")

graph.add_edge("classifier", "processor")
graph.add_edge("processor", "validation")
graph.add_edge("validation", "risk")
graph.add_edge("risk", "decision")

graph.add_edge("decision", END)

workflow = graph.compile()
