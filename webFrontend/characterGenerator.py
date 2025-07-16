import dataProvider
import logger
import models
import chatModel
import config
from webFrontend.extensionHandler import ToolsHandler
import workflowTools

class CharacterGenerator:
    def __init__(self, dataProvider: dataProvider.DataProvider):
        self.dataProvider = dataProvider
        
    def generate(self, name: str) -> dict[str, str]:
        """
        Create a new character with the given name and collected information through AI

        Args:
            name (str): The character's name.

        Returns:
            dict[str, str]: A dictionary containing the generated character's information including `charName`, `charPrompt`, `initalMemory`, `exampleChats`.
        """
        self.toolsHandler = ToolsHandler(None, self.dataProvider, workflowTools.AvailableTools(), [])
        self.prompt = models.PreprocessPrompt(config.CREATE_CHARACTER_PROMPT, {
            'charName': name,
            'toolsPrompt': models.PreprocessPrompt(config.TOOLS_PROMPT, {
                'generated_tool_descriptions': self.toolsHandler.generated_tool_descriptions,
                'extra_info': self.toolsHandler.generated_extra_infos
            })
        })
        self.llm = models.ThinkingModelProvider('')
        self.toolsHandler.bindLLM(self.llm)
        
        generated = {
            'charName': None,
            'charPrompt': None,
            'initalMemory': None,
            'exampleChats': []
        }
        
        def handleIntent(intent: str, args: str):
            logger.Logger.log(f'Intent: {intent}, Args: {args}')
            match intent:
                case 'charname':
                    generated['charName'] = args
                case 'charprompt':
                    generated['charPrompt'] = args
                case 'initalmemories':
                    generated['initalMemory'] = args
                case 'examplechats':
                    generated['exampleChats'].append(args)
                case _:
                    pass
        
        self.toolsHandler.on('unhandled_intent', handleIntent)
        self.toolsHandler.handleRawResponse(self.llm.initiate(self.prompt + '\nNow let the creation begin!'))
        
        return generated
        