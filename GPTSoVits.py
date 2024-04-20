import requests


class GPTSoVitsAPI():
    def __init__(self, api_url: str) -> None:
        self.api_url = api_url
        pass

    # text to speech
    def tts(self, ref_audio: str, ref_text: str, text: str, ref_language: str = 'auto', text_language: str = 'auto') -> requests.Response:
        return requests.post(f'{self.api_url}/', json={
            "refer_wav_path": ref_audio,
            "prompt_text": ref_text,
            "prompt_language": ref_language,
            "text": text,
            "text_language": text_language
        }, stream=True)

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
