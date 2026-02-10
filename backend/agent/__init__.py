from .abstract_agent import Agent
from .basic_chatting_agent import BasicChattingAgent
from .lecture_agent import LectureAgent
from config_types import LLM_Config

REGISTRY = {
    "basic_chatting_agent": BasicChattingAgent,
    "lecture_agent": LectureAgent,
}

def create_agent(agent_type: str, server_url: str, agent_name: str, llm_api_config: LLM_Config | None = None, **kwargs) -> Agent:
    if agent_type not in REGISTRY:
        raise ValueError(f"Unknown agent type: {agent_type}")
    if llm_api_config is None:
        return REGISTRY[agent_type](server_url = server_url, agent_name = agent_name, **kwargs)
    return REGISTRY[agent_type](server_url = server_url, agent_name = agent_name, llm_api_config = llm_api_config, **kwargs)
