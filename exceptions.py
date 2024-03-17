class CharacterNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class SessionNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class MaxRetriesExceeded(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)