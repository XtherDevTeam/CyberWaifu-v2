# preserve the original module name to make it compatible with the DeeperResearch extensions.

import os
import chatModel
import pathlib
import requests
import bs4
import googleapiclient.discovery
import tools
import urllib.parse
import typing
import dataProvider
import logger
import subprocess
import sys
import importlib
import google.genai.types
import config

class ToolResponse:
    def __init__(self, content: typing.Any, type: str = 'text/plain'):
        self.response_content = content
        self.type = type
        
    def asModelInput(self):
        if self.type in ['text/plain', 'list', 'dict']:
            return str(self.response_content)
        elif self.type.startswith('image/') or self.type.startswith('video/') or self.type.startswith('audio/'):
            if isinstance(self.response_content, str):
                self.response_content = pathlib.Path(self.response_content).read_bytes()
                
            return google.genai.types.Part.from_bytes(
                data=self.response_content,
                mime_type=self.type,
            )
        elif type in ['gemini/file-object']:
            return self.response_content
        
    
    def asReadableObject(self) -> dict | str:
        if self.type.startswith('image/') or self.type.startswith('video/') or self.type.startswith('audio/'):
            return {
                'type': 'attachment',
                'mime_type': self.type,
            }
        elif self.type in ['text/plain', 'list', 'dict']:
            return self.response_content
        else:
            return {
                'type': 'unknown',
                'content': str(self.response_content),
                'mime_type': self.type,
            }
            
            
    def __str__(self):
        return f'ToolResponse(type={self.type}, content={self.asReadableObject()})'
        
        
class TextResponse(ToolResponse):
    def __init__(self, content: str):
        super().__init__(content, 'text/plain')


class ImageResponse(ToolResponse):
    def __init__(self, content: bytes, mime: str = 'image/jpeg'):
        super().__init__(content, mime)


class AudioResponse(ToolResponse):
    def __init__(self, content: bytes, mime: str = 'audio/mpeg'):
        super().__init__(content, mime)
            


def WebsiteReader(url: str) -> dict[str, list[dict] | str]:
    """
    Tool for reading website readable content.

    Args:
        url (str): The website url to read.

    Returns:
        dict[str, list[dict] | str]: A dictionary containing the website content and links as a list of dictionaries.
        For key `content`, the value is the text content of the website. For key `links`, the value is a list of dictionaries
    """
    userAgent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0'
    
    def get_website_content(url: str) -> bytes:
        resp = requests.get(url, headers={'User-Agent': userAgent}, timeout=1240)
        if resp.status_code != 200:
            raise Exception(f'Failed to read website {url}. Status code: {resp.status_code}. You may retry later.')
        return resp
    
    resp = tools.retryWrapper(lambda: get_website_content(url), max_retries=5, retry_interval=1)
    
    print(resp)
    content = resp.content
    soup = bs4.BeautifulSoup(content, 'html.parser')
    if 'fandom.com' in url:
        # get the .page section of the fandom page
        page_soup = soup.find('div', class_='page')
        if page_soup:
            soup = page_soup

    all_text = soup.get_text()

    gathered_links = []
    for link in soup.find_all('a'):
        text = link.parent.get_text()
        href = link.get('href')
        if href:
            if href.startswith('http'):
                gathered_links.append({
                    'content': text,
                    'url': href,
                })
            elif href.startswith('/'):
                # extract the host from url and add the href to it
                new_url = urllib.parse.urljoin(url, href)
                gathered_links.append({
                    'content': text,
                    'url': new_url,
                })
            else:
                # ignore relative links
                pass

    return TextResponse({
        'content': all_text,
        'links': gathered_links,
    })


def SearchEngine(query: str, page: int = 1) -> list[dict[str, str]]:
    """
    Tool for searching for information on the internet.
    You may use this to find related information with user's given instruction. 
    After gathering brief information through this tool, you should find out a list of websites that are related to the user's instruction, and access them to provide more information.

    Args:
        query (str): The query to search for.
        page (int): The page number to search for. Defaults to 1.

    Returns:
        list[dict[str, str]]: A list of dictionaries containing the search results.
    """

    # Set up the Google Custom Search API
    api_key = os.environ.get('google_search_engine_key')
    cse_id = os.environ.get('google_search_engine_cx_id')
    service = googleapiclient.discovery.build(
        'customsearch', 'v1', developerKey=api_key)

    # Search for the query
    res = service.cse().list(q=query, cx=cse_id, num=10, start=10*(page-1)).execute() # support page indexing
    results = []
    for item in res['items']:
        title = item['title']
        link = item['link']
        snippet = item['snippet']
        results.append({'title': title, 'link': link, 'snippet': snippet})
    return TextResponse(results)


def AvailableTools() -> list[typing.Callable]:
    """
    Returns a list of available tools.

    Returns:
        list[typing.Callable]: A list of available tools.
    """

    return [
        WebsiteReader,
        SearchEngine,
    ]


def ConvertTypeToStr(type_obj: typing.Any) -> str:
    """
    Convert a type object to a string representation.

    Args:
        type_obj (typing.Any): The type object to convert.

    Returns:
        str: The string representation of the type object.
    """

    if type_obj == str:
        return 'str'
    elif type_obj == int:
        return 'int'
    elif type_obj == float:
        return 'float'
    elif type_obj == bool:
        return 'bool'
    elif type_obj == list:
        return 'list'
    elif type_obj == dict:
        return 'dict'
    else:
        return str(type_obj)


def GetToolDescription(tool: typing.Callable) -> dict[str, str] | None:
    """
    Extract the method name, parameters and return type and description of a tool from callable definition.
    Args:
        tool (typing.Callable): The tool to extract the description from.

    Returns:
        dict[str, str] | None: A dictionary containing the method name, parameters and return type and description of the tool.
    """

    # Extract the method name, parameters and return type
    method_name = tool.__name__
    parameters = {}
    for parameter in tool.__annotations__.items():
        if parameter[0] == 'return':
            continue
        parameters[parameter[0]] = ConvertTypeToStr(parameter[1])
    return_type = ConvertTypeToStr(tool.__annotations__.get('return'))

    # Extract the description from the docstring
    docstring = tool.__doc__
    if docstring is None:
        return None
    description = docstring.strip()

    return {
        'tool': method_name,
        'params': parameters,
        'return_type': return_type,
        'description': description,
    }
    

def GetToolReadableDescription(tool: typing.Callable) -> str:
    """
    Extract the method name, parameters and return type and description of a tool from callable definition and format it as a readable string.
    Args:
        tool (typing.Callable): The tool to extract the description from.

    Returns:
        str: A string containing the method name, parameters and return type and description of the tool.
    """

    description = GetToolDescription(tool)
    desc = f'### {description['tool']}\n\n'
    desc += f'**Invocation name**: `{description["tool"]}`\n\n'
    desc += f'**Params**: \n'
    for param_name, param_type in description['params'].items():
        desc += f'  - `{param_name}` ({param_type})\n'
    desc += '\n'
    desc += f'**Return type**: {description["return_type"]}\n\n'
    desc += f'**Description**: {description["description"]}\n\n'
    desc += '\n'
    return desc

def loadOrReportMissingImport(module_name: str, version: str = '*') -> None:
    try:
        return importlib.import_module(module_name)
    except ImportError:
        res = input(f'Missing import: {module_name}, do you wish to run `pip install {module_name}`? (y/n)')
        if res.lower() == 'y':
            subprocess.run([sys.executable, "-m", "pip", "install", f"{module_name}=={version}" if version != '*' else module_name])
            return importlib.import_module(module_name)
        elif res.lower() == 'n':
            print(f'Skipping import {module_name}, this may cause some features to be unavailable.')
        else:
            print(f'Invalid input: {res}. Skipping import {module_name}.')