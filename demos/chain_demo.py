"""Plain LangChain chain called three times with a growing conversation."""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from fake_model import FakeCachingChat

model = FakeCachingChat(script=lambda ms: AIMessage(content=f"Answer #{len(ms)}: " + "lorem ipsum " * 20))
history = [SystemMessage(content="You are a helpful travel assistant. " * 60)]
for q in ["Plan a trip to Lisbon", "Add food recommendations", "What about day trips?"]:
    history.append(HumanMessage(content=q))
    history.append(model.invoke(history))
print("done:", len(history), "messages")
