class CharacterNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class EventNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class SessionNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class SessionHasAlreadyExist(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class MaxRetriesExceeded(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class StickerNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class NoUserMediaFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class ReferenceAudioNotFound(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)
        
class UnsupportedMimeType(RuntimeError):
    def __init__(self, s) -> None:
        super().__init__(s)