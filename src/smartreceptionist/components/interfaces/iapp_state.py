from abc import ABC, abstractmethod


class IAppState(ABC):
    @abstractmethod
    def get_gate_state(self):
        pass

    @abstractmethod
    def get_light_state(self):
        pass
