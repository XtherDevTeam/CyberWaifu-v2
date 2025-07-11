import typing
import logger
import workflowTools

class UserScript():
    def __init__(self, name, script):
        logger.Logger.log(f'[Script/{name}]: Creating user script environment')
        self.globals = {workflowTools.__name__: workflowTools}
        self.script = script
        self.name = name
        self.bc = compile(script, f'<string>', 'exec')
        exec(self.bc, self.globals, self.globals)
        logger.Logger.log(f'[Script/{name}]: User script environment created')
        if 'register' not in self.globals:
            logger.Logger.error(f'[Script/{name}]: No register function found in user script')
            raise NotImplementedError('No register function found in user script')

        info = self.invoke('register')
        for i in info:
            if not callable(info[i]):
                logger.Logger.error(f'[Script/{name}]: Register function returned non-callable {info[i]}')
                raise TypeError('Register function returned non-callable')

        
        self.readable_information = {i: workflowTools.GetToolReadableDescription(info[i]) for i in info}
        
    def getReadableInformation(self):
        return '\n'.join(f'{v}' for k, v in self.readable_information.items())

    def invoke(self, key: str, *args, **kwargs) -> typing.Any:
        if key not in self.globals:
            raise KeyError(f'[Script/{self.name}]: No invocable function found for key {key}')

        func = self.globals[key]

        return func(*args, **kwargs)

    def getInvocable(self, key: str) -> typing.Callable:
        return lambda *args, **kwargs: self.invoke(key, *args, **kwargs)

    def getAllInvocables(self) -> list[str]:
        return [i for i in self.readable_information.keys()]