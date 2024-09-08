from langchain_core.messages import HumanMessage, SystemMessage, RemoveMessage
from langgraph.graph import MessagesState
from typing import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import PromptTemplate
from langgraph.prebuilt import tools_condition, ToolNode
from typing import Literal

# We will use this model for both the conversation and the summarization
from langchain_openai import ChatOpenAI
model = ChatOpenAI(model="gpt-4o", temperature=0)
def add(a: int, b: int) -> int:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiplies a and b.

    Args:
        a: first int
        b: second int
    """
    return a * b

def divide(a: int, b: int) -> float:
    """Adds a and b.

    Args:
        a: first int
        b: second int
    """
    return a / b

tools = []
llm = ChatOpenAI(model="gpt-4o")
tools = [add, multiply, divide]
llm_with_tools = llm.bind_tools(tools)


class State(MessagesState):
    next_node: str

def get_router_template():
    return PromptTemplate.from_template(
            """
            You are an AI Assistant that is specialized in research of the real estate market of Hyderabad, India. Your Name is MARCUS created by clear-estate.com.
            Given the user current question and chat history below, classify which agent is most appropriate to best help with this
            `analysis`: Any queries to calculate and solve real estate problems like calculating land/property valuations of the users. Calculate mean, median and any statistical problems related to real estate.
            `insights`: Any queries related to finding the current rates, trends, ROI and releated questions regarding current and past real estate questions.
            `property`: Any queries related to finding a property, trying to find a place with specific requirements. Direct any property search or place search questions here.
            `generic`:  Any queries not related to real estate, about MARCUS which is the product and anything that does not fit the above.
            Do not respond with more than one word.
            <question>
            {input}
            </question>
            <histroy>
            {chat_history}
            </history>

        Classification:"""
        )

def router(state: State):
   chain = (
            get_router_template()
            | ChatAnthropic(model_name="claude-3-haiku-20240307")
            | StrOutputParser()
        )
   return {"next_node": chain.invoke({"input": state["messages"][-1], "chat_history": state["messages"]})}

# System message
sys_msg = SystemMessage(content="You are a helpful assistant answer the questions")

# Node
def property_assistant(state):
   return {"messages": [llm_with_tools.invoke([sys_msg] + state["messages"])]}


def sub_agent_condition(state) -> Literal['insights_search_agent', 'property_search_agent', '__end__']:
    if state["next_node"] == 'property':
        return 'property_search_agent'
    elif state["next_node"] == 'insights':
        return 'insights_search_agent'
    else:
        return '__end__'

# Define a new graph
workflow = StateGraph(State)
workflow.add_node("marcus_router", router)
workflow.add_node("insights_search_agent", property_assistant)
workflow.add_node("property_search_agent", property_assistant)


# add edges
workflow.add_edge(START, "marcus_router")
workflow.add_conditional_edges("marcus_router", sub_agent_condition)
workflow.add_edge("insights_search_agent", END)
workflow.add_edge("property_search_agent", END)
# Compile
graph = workflow.compile()