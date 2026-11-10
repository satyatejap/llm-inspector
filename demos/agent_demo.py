"""LangGraph ReAct agent with a tool, two user turns; the second turn breaks the cache prefix."""
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from fake_model import FakeCachingChat


@tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"Sunny, 22C in {city}. " + "details " * 40


def script(messages):
    if messages[-1].type == "tool":
        return AIMessage(content="It is sunny and warm. " + "Enjoy! " * 10)
    return AIMessage(content="", tool_calls=[{"name": "get_weather", "args": {"city": "Paris"}, "id": f"c{len(messages)}"}])


agent = create_react_agent(FakeCachingChat(script=script), [get_weather], prompt="You are a weather bot. " * 80)
for q in ["Weather in Paris?", "And what should I wear there?"]:
    r = agent.invoke({"messages": [("user", q)]})
    print(r["messages"][-1].content[:40])
