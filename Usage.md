# Prerequisite

1. First initialize conda environment by executing `initialize.sh`
2. Attain an api key from [Google AI Studio](https://aistudio.google.com)
3. If you are going to use a fine-tuning model, finish these [steps](https://ai.google.dev/palm_docs/oauth_quickstart?hl=zh-cn) and copy the `client_secret.json` under the project root directory.
4. Add your api key into project by editing `config.py`

# Add a new character

1. Complete the prerequisite steps
2. Prepare a small introduction of your character like `test/yoi_prompt.txt`
3. Prepare a piece of character initial memory like `test/yoi_memory.txt`
4. Activate conda environment by executing `conda activate cyberWaifuV2`
5. Execute `python app.py --new` to create a new character in accordance with instructions

# Command-line conversation frontend interface

1. Complete the prerequisite steps and make sure you have already added your character
2. Execute `python app.py -c [charName] -u [yourName] -f`