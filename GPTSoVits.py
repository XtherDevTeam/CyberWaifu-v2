import requests

import logger


class GPTSoVitsAPI():
    """
    GPTSoVits API class.

    Attributes:
        api_url (str): Url of the GPTSoVits API.
        usingV3 (bool): whether using APIv3.py from the fast_inference_ branch.
        ttsInferYamlPath (str): GPT weights path. Necessary for v3 API.

    Methods:
        tts_v1(ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response: Run TTS inference using the classic v1 API.
        tts_v3(ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response: Run TTS inference using the v3 API from the fast_inference_ branch.
        tts(ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response: Run TTS inference based on the API version.
        changeReferenceAudio(ref_audio: str, ref_text: str, ref_language: str = 'auto') -> None: Change reference audio.
        control(command: str): Restart or exit.
    """

    def __init__(self, api_url: str, isTTSv3: bool = False, ttsInferYamlPath: str = "") -> None:
        """
        Initialize the GPTSoVitsAPI.

        Args:
            api_url (str): Url of the GPTSoVits API.
            isTTSv3 (bool): whether using APIv3.py from the fast_inference_ branch. Defaults to False.
            gptWeightsPath (str): GPT weights path. Necessary for v3 API. Defaults to "".
            sovitsWeightsPath (str): SoVits weights path. Necessary for v3 API. Defaults to "".
        """
        self.api_url = api_url
        self.usingV3 = isTTSv3
        self.ttsInferYamlPath = ttsInferYamlPath
        if isTTSv3:
            logger.Logger.log('Using v3 API from the fast_inference_ branch')
        else:
            logger.Logger.log('Using classic v1 API from the main branch')


    # text to speech function for v1 API
    def tts_v1(self, ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response:
        """
        Run TTS inference using the classic v1 API.

        Args:
            ref_audio (str): Reference audio path.
            ref_text (str): Reference text.
            text (str): Text to be synthesized.
            ref_language (str, optional): Reference audio language. Defaults to 'auto'.
            text_language (str, optional): Text language. Defaults to 'auto'.

        Returns:
            requests.Response: Response object from the API.
        """
        return requests.post(f'{self.api_url}/', json={
            "refer_wav_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_language": ref_language,
            "text": text,
            "text_language": text_language
        }, stream=True)

    def tts_v3(self, ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response:
        """
        Run TTS inference using the v3 API from the fast_inference_ branch.

        Args:
            ref_audio (str): Reference audio path. Should be less than 10 seconds long.
            ref_text (str): Reference text.
            text (str): Text to be synthesized.
            ref_language (str, optional): Reference audio language. Defaults to 'auto'.
            text_language (str, optional): Text language. Defaults to 'auto'.

        Returns:
            requests.Response: Response object from the API.
        """
        return requests.get(f'{self.api_url}/tts', params={
            "text": text,
            "text_lang": text_language,
            "ref_audio_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_lang": ref_language,
            "media_type": "aac",
            "streaming_mode": True,
            "parallel_infer": True,
            "tts_infer_yaml_path": self.ttsInferYamlPath
        })

    def tts(self, ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response:
        """
        Run TTS inference based on the API version.

        Args:
            ref_audio (str): Reference audio path.
            ref_text (str): Reference text.
            text (str): Text to be synthesized.
            ref_language (str, optional): Reference audio language. Defaults to 'auto'.
            text_language (str, optional): Text language. Defaults to 'auto'.

        Returns:
            requests.Response: Response object from the API.
        """
        if self.usingV3:
            return self.tts_v3(ref_audio, ref_text, text, ref_language, text_language)
        else:
            return self.tts_v1(ref_audio, ref_text, text, ref_language, text_language)

    # change reference audio
    def changeReferenceAudio(self, ref_audio: str, ref_text: str, ref_language: str = 'auto') -> None:
        r = requests.post(f'{self.api_url}/change_ref', json={
            "refer_wav_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_language": ref_language
        })
        if r.status_code == 400:
            raise RuntimeError(f'{__name__}: Failed to change reference audio')
        else:
            return

    # restart or exit
    def control(self, command: str):
        requests.post(f'{self.api_url}/control', json={
            "command": command})
