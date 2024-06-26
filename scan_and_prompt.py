import os, chatModel


text = ''

def add_file(file_path: str):
    global text
    with open(file_path, 'r+') as f:
        text += f'''\
- `{file_path}`
```
{f.read()}
```
'''

def walk(path: str = '.'):
    for i in os.listdir(path):
        p = os.path.join(path, i)
        if os.path.isdir(p):
            walk(p)
        elif os.path.splitext(p)[1] in ['.py', '.sql', '.md']:
            add_file(p)
            
            
def generate():
    global text
    text = '''\
You are an backend engineer, you are provided with the source code of project CyberWaifu-v2.
Generate an GitHub README.md of this project.

Guidelines:

- Carefully read the source code of this project. Figure out the function of each file.
- Think of the mechanism of this project, such as how does it store character informations and memories, and how does it use the memories and prompts.
- Summarize it into an concise and vivid introduction.

Let the show begin!

'''
    walk()
    
if __name__ == '__main__':
    model = chatModel.ChatGoogleGenerativeAI('gemini-1.5-pro-latest', 1)
    generate()
    print(model.initiate(text))