"""Home State Agent (Digital Twin) -- manages device state with LangChain tools."""

import logging
import uuid
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from config import settings
from src.agents.base import BaseAgent, AgentStatus
from src.agents.tools.device_tools import DEVICE_TOOLS
from src.agents.tools.query_tools import QUERY_TOOLS
from src.devices.registry import device_registry
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Home State Agent (Digital Twin) for a smart home system.
You maintain the complete state of all devices and execute actions.

Your responsibilities:
- Execute device control commands accurately
- Validate all inputs before executing (e.g., temperature ranges)
- Query device states when needed
- Provide clear feedback on action results

Available rooms: living_room, bedroom, kitchen, office, front_door, energy_system

When executing commands:
1. First understand what needs to be done
2. Use the appropriate tool(s) to execute
3. Verify the result
4. Return a clear summary

Always be precise with device IDs and parameters."""


class HomeStateAgent(BaseAgent):
    """Digital Twin agent that manages all device states via LangChain tools."""

    def __init__(self):
        super().__init__("home_state", "Home State Agent (Digital Twin)")
        self._all_tools = DEVICE_TOOLS + QUERY_TOOLS
        self._agent_executor: AgentExecutor | None = None

    async def start(self) -> None:
        await super().start()
        self._setup_agent()

    def _setup_agent(self) -> None:
        """Initialize the LangChain agent with tools."""
        try:
            llm = ChatOpenAI(
                model=settings.openrouter_default_model,
                openai_api_key=settings.openrouter_api_key,
                openai_api_base=settings.openrouter_base_url,
                temperature=0.1,
                max_tokens=1500,
            )

            prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content=SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                HumanMessage(content="{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])

            agent = create_tool_calling_agent(llm, self._all_tools, prompt)
            self._agent_executor = AgentExecutor(
                agent=agent,
                tools=self._all_tools,
                verbose=settings.debug,
                max_iterations=5,
                handle_parsing_errors=True,
            )
            logger.info("Home State Agent LangChain agent initialized")
        except Exception as e:
            logger.error(f"Failed to setup LangChain agent: {e}")
            self._agent_executor = None

    async def run(self, instruction: str) -> dict[str, Any]:
        """Execute an instruction using the LangChain agent."""
        self._status = AgentStatus.RUNNING

        try:
            if self._agent_executor:
                result = await self._agent_executor.ainvoke({"input": instruction})
                output = result.get("output", "No output")
            else:
                # Fallback: direct tool execution based on parsing
                output = await self._direct_execute(instruction)

            self._record_action(
                action=f"Executed: {instruction[:100]}",
                reasoning=output[:500],
            )

            # Log event
            await event_store.log_event(Event(
                event_id=str(uuid.uuid4())[:8],
                event_type=EventType.AGENT_DECISION,
                source=self.agent_id,
                data={"instruction": instruction, "result": output[:500]},
            ))

            # Broadcast update
            await ws_manager.broadcast("agent_action", {
                "agent_id": self.agent_id,
                "action": instruction[:100],
                "result": output[:200],
            })

            self._status = AgentStatus.IDLE
            return {"success": True, "output": output}

        except Exception as e:
            logger.error(f"Home State Agent error: {e}")
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return {"success": False, "error": str(e)}

    async def _direct_execute(self, instruction: str) -> str:
        """Fallback direct execution without LLM when API is unavailable."""
        instruction_lower = instruction.lower()

        # Simple keyword-based routing
        if "turn off" in instruction_lower or "switch off" in instruction_lower:
            for device in device_registry.devices.values():
                if device.display_name.lower() in instruction_lower or device.device_id in instruction_lower:
                    result = await device.execute_action("off")
                    return f"Turned off {device.display_name}: {result}"

        elif "turn on" in instruction_lower or "switch on" in instruction_lower:
            for device in device_registry.devices.values():
                if device.display_name.lower() in instruction_lower or device.device_id in instruction_lower:
                    result = await device.execute_action("on")
                    return f"Turned on {device.display_name}: {result}"

        elif "status" in instruction_lower or "state" in instruction_lower:
            states = device_registry.get_all_states()
            return f"Current home state: {len(device_registry.devices)} devices loaded"

        return f"Could not parse instruction without LLM: {instruction}"

    async def execute_action(self, device_id: str, action: str, params: dict = {}) -> dict[str, Any]:
        """Directly execute an action on a device (used by Orchestrator)."""
        device = device_registry.get_device(device_id)
        if not device:
            return {"success": False, "error": f"Device not found: {device_id}"}

        result = await device.execute_action(action, params)

        # Log and broadcast
        await event_store.log_event(Event(
            event_id=str(uuid.uuid4())[:8],
            event_type=EventType.DEVICE_COMMAND,
            source=device_id,
            data={"action": action, "params": params, "result": result},
        ))
        await ws_manager.broadcast("device_state", device.get_state_dict())

        self._record_action(
            action=f"{device_id}.{action}({params})",
            reasoning=f"Direct execution result: {result}",
        )

        return result

    def get_all_states(self) -> dict[str, Any]:
        """Get all device states."""
        return device_registry.get_all_states()

    def get_energy_summary(self) -> dict[str, Any]:
        """Get energy summary."""
        return device_registry.get_energy_summary()


# Singleton
home_state_agent = HomeStateAgent()
