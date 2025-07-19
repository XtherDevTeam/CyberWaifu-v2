import bs4
import dataProvider
import logger
import time
import chatModel
import config
import tools
import uuid
import workflowTools
import typing
import json
from userScript import UserScript
import google.genai.live

class ToolsHandler:
    def __init__(self, llm: chatModel.ChatGoogleGenerativeAI, dataProvider: dataProvider.DataProvider, enabled_tools: list[typing.Callable] = [], enabled_user_scripts: list[dict[str, str]] = []):
        """
        Initialize the ToolsHandler class

        Args:
            llm (chatModel.ChatGoogleGenerativeAI): The chat model object
            dataProvider (dataProvider.DataProvider): The data provider object
        """
        self.llm = llm
        self.available_events = {
            'intermediate_response': [],
            'unhandled_intent': [],
            'terminate_intent': []
        }
        self.dataProvider = dataProvider
        self.generated_tool_descriptions = ''.join(
            [workflowTools.GetToolReadableDescription(i) for i in enabled_tools])
        self.generated_extra_infos = ''.join([i['content'] for i in self.dataProvider.getAllEnabledExtraInfos()])
        
        self.enabled_tools = enabled_tools
        self.parsed_user_scripts: list[UserScript] = []
        
        
        self.enabled_tools_mapping = {
            i.__name__: i for i in self.enabled_tools}

        self.enabled_user_script_tool_mapping = {}

        for i in enabled_user_scripts:
            name, content = i['name'], i['content']
            script = UserScript(name, content)
            self.parsed_user_scripts.append(script)

            for tool in script.getAllInvocables():
                self.enabled_user_script_tool_mapping[tool] = script.getInvocable(
                    tool)

            self.generated_tool_descriptions += script.getReadableInformation()

        logger.Logger.log(f'Enabled user scripts: {self.parsed_user_scripts}')
        logger.Logger.log(
            f'Enabled user script tool mapping: {self.enabled_user_script_tool_mapping}')

    def on(self, event: str, callback: typing.Callable) -> None:
        """
        Register a callback function to be called when an event is triggered.

        Args:
            event (str): The event to register the callback for.
            callback (typing.Callable): The callback function to be called.
        """
        if event in self.available_events:
            self.available_events[event].append(callback)
        else:
            raise ValueError(f'Invalid event: {event}')
        
    def trigger(self, event: str, *args, **kwargs) -> None:
        """
        Trigger an event and call all registered callback functions.

        Args:
            event (str): The event to trigger.
        """
        if event in self.available_events:
            for callback in self.available_events[event]:
                callback(*args, **kwargs)
        else:
            raise ValueError(f'Invalid event: {event}')

    def bindLLM(self, llm: chatModel.ChatGoogleGenerativeAI) -> None:
        """
        Bind the LLM to the ToolsHandler.

        Args:
            llm (chatModel.ChatGoogleGenerativeAI): The chat model object.
        """
        self.llm = llm
    
    def parseRawResponse(self, response: str) -> dict[str, str]:
        """
        Parse the raw response from the LLM and extract tool invocations.

        Args:
            response (str): The raw response from the LLM.

        Returns:
            dict[str, str]: The parsed responses with two keys: `response` and `intents`.
        """
        print(response)
        if '<intents>' in response:
            intents = response[response.find(
                '<intents>'):response.rfind('</intents>')+10]
            # exclude the intents content from the response
            response = response[:response.find(
                '<intents>')] + response[response.rfind('</intents>')+10:]
            print(intents)
            parsed_intents = bs4.BeautifulSoup(intents, 'html.parser')
            # find out all invocation tags
            tags = []
            try:
                for i in parsed_intents.find_all('intents')[0].findChildren():
                    try:
                        tags.append({
                            'name': i.name,
                            'content': json.loads(i.text)
                        })
                    except:
                        tags.append({
                            'name': i.name,
                            'content': i.text
                        })
            except Exception as e:
                raise e
                # return {
                #     "response": f"Failed to parse intents: {e}",
                #     "intents": {},
                # }
            return {
                "response": response,
                "intents": tags,
            }
        else:
            return {
                "response": response,
                "intents": {},
            }

    def handleIntent(self, intent: str, args: dict[str, str]) -> dict[str, str] | None:
        """
        Handle an intent by calling the corresponding tool, and return the response generated by the tool.

        Intents handled by the chat model:
            - "invocation": call the corresponding tool with the given arguments, and return the result.

        Args:
            intent (dict[str, str]): The intent to handle.
            args (dict[str, str]): The arguments supplied for the intent.

        Returns:
            dict[str, str] | None: The response generated by the tool, or None if the intent is not handled.
        """
        match intent:
            case "invocation":
                logger.Logger.log(f'Handling intent {intent} with args {args}')
                params = args.get('params', {})
                try:
                    if args['tool'] in self.enabled_tools_mapping:
                        invocation_result = self.enabled_tools_mapping[args['tool']](
                            **params)
                    elif args['tool'] in self.enabled_user_script_tool_mapping:
                        invocation_result = self.enabled_user_script_tool_mapping[args['tool']](
                            **params)
                    else:
                        invocation_result = {
                            "status": "failed",
                            "message": f"Invalid tool: {args['tool']}, available tools are: {list(self.enabled_tools_mapping.keys()) + list(self.enabled_user_script_tool_mapping.keys())}",
                        }
                except Exception as e:
                    invocation_result = {
                        "status": "failed",
                        "message": f"Failed to invoke tool: {e}",
                    }
                logger.Logger.log(
                    f'Handling intent {intent} with params {params} and result {invocation_result}')
                return {
                    "invocation": args,
                    "result": invocation_result,
                }
            case "terminate":
                # invoke hook
                logger.Logger.log(f'Handling intent {intent} with args {args}')
                self.trigger('terminate_intent', args)
                return None
            case _:
                self.trigger('unhandled_intent', intent, args)
                return None

    def handleRawResponse(self, response: str) -> str:
        """
        Handle a raw response from the LLM by parsing the response and handling the intents.

        Args:
            response (str): The raw response from the LLM.

        Returns:
            (str | None): The response generated by the tools. If no intents are found, return None.
        """
        
        if self.llm is None:
            logger.Logger.log(f'No chat model bound to the ToolsHandler, handleRawResponse will be disabled!')
            return None
        
        current_response = self.parseRawResponse(response)
        
        while current_response['intents']:
            logger.Logger.log(f'Handling response: {current_response}')
            intent_results = []
            for i in current_response['intents']:
                intent_result = self.handleIntent(i['name'], i['content'])
                if intent_result and 'result' in intent_result:
                    intent_results.append(intent_result['result'])
                elif intent_result:
                    intent_results.append(intent_result)
            
            if intent_results:
                prompt = [r.asModelInput() if isinstance(
                    r, workflowTools.ToolResponse) else str(r) for r in intent_results]
                current_response = self.parseRawResponse(self.llm.chat(prompt))
                self.trigger('intermediate_response', current_response['response'])
            else:
                break
            
        return current_response['response']
