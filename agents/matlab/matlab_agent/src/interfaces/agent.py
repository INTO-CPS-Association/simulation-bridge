"""MATLAB agent interface compatibility wrapper."""

from base_agent.interfaces.agent import IAgent


class IMatlabAgent(IAgent):
    """MATLAB-specific alias for the shared agent interface."""
