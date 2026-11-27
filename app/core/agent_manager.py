from datetime import datetime, timezone
from app.models.agent import Agent, AgentStatus


class AgentManager:

    def __init__(self):
        self.agents = {}

    def register_agent(self, agent_id: str, agent_name: str):

        if agent_id in self.agents:
            raise ValueError("Agent already registered")

        agent = Agent(
            agent_id=agent_id,
            agent_name=agent_name,
            status=AgentStatus.READY,
            last_heartbeat=datetime.now(timezone.utc)
        )

        self.agents[agent_id] = agent

        return agent

    def get_all_agents(self):
        return list(self.agents.values())

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)


agent_manager = AgentManager()