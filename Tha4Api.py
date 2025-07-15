import requests
import json
import typing

class Tha4Api:
    """
    API client for the THA4 Live2D Realtime Session Manager Flask middleware.

    This class provides methods to interact with the Flask server endpoints
    for establishing, shutting down, and compiling Live2D sessions and assets.
    """

    def __init__(self, base_url: str = 'http://localhost:3623'):
        """
        Initializes the Tha4Api client.

        Args:
            base_url: The base URL of the Flask API server.
                      Defaults to 'http://localhost:3623'.
        """
        # Ensure base_url ends with a slash for consistent path joining
        self.base_url = base_url.rstrip('/') + '/'

    def _make_request(self, method: str, endpoint: str, **kwargs: typing.Any) -> typing.Dict[str, typing.Any]:
        """
        Helper method to make HTTP requests and handle standard API responses.

        Args:
            method: The HTTP method (e.g., 'POST').
            endpoint: The API endpoint path (e.g., 'establish_session').
            kwargs: Additional arguments to pass to requests.request (e.g., data, files, json, timeout).

        Returns:
            The full JSON response dictionary from the API if 'status' is True.

        Raises:
            ConnectionError: If unable to connect to the API server.
            TimeoutError: If the API request times out.
            requests.exceptions.RequestException: For other HTTP-related errors (e.g., 4xx, 5xx status codes).
            json.JSONDecodeError: If the response is not valid JSON.
            ValueError: If the API call returns status: False with an error message.
        """
        url = self.base_url + endpoint
        try:
            # Add a default timeout to prevent indefinite waiting
            kwargs.setdefault('timeout', 30) # 30 seconds default timeout

            response = requests.request(method, url, **kwargs)
            response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

            response_json = response.json()
            if not response_json.get('status', False):
                # The Flask app's Result function includes an error message in 'data'
                error_data = response_json.get('data', 'Unknown error from API')
                raise ValueError(f"API call failed for {endpoint}: {error_data}")
            return response_json
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to API server at {url}. Please ensure the server is running and accessible: {e}")
        except requests.exceptions.Timeout as e:
            raise TimeoutError(f"API request timed out for {url}: {e}")
        except requests.exceptions.RequestException as e:
            # This covers HTTPError (from raise_for_status), TooManyRedirects, etc.
            status_code_info = f" (Status Code: {e.response.status_code})" if e.response is not None else ""
            try:
                # Attempt to get error message from JSON response if available
                error_details = e.response.json().get('data', '') if e.response else ''
                if error_details:
                    error_details = f" Details: {error_details}"
            except (json.JSONDecodeError, AttributeError):
                error_details = ''
            raise requests.exceptions.RequestException(f"API request failed for {url}{status_code_info}{error_details}: {e}")
        except json.JSONDecodeError as e:
            # If the response is not JSON, or malformed JSON
            raw_response = response.text if 'response' in locals() else 'No response text available.'
            raise json.JSONDecodeError(f"Failed to decode JSON response from {url}: {e}. Raw response: {raw_response}", doc=raw_response, pos=0)
        except ValueError as e:
            # Re-raise the custom API failure message (status: False)
            raise e

    def establish_session(
        self,
        configuration: typing.Dict[str, typing.Any],
        avatar: bytes,
        base_fps: typing.Optional[int] = None,
        live2d_token: typing.Optional[str] = None,
        livekit_url: typing.Optional[str] = None
    ) -> str:
        """
        Invokes the /establish_session endpoint to create a new Live2D session.

        This endpoint expects form-data for configuration, baseFps, tokens,
        and a file upload for the avatar.

        Args:
            configuration: A dictionary representing the Live2D configuration.
            avatar: The bytes of the avatar model (e.g., .zip, .moc3, .cmo3).
            base_fps: The base frames per second for the session. Optional.
            live2d_token: Token for Live2D authentication. Optional.
            livekit_url: URL for Livekit connection. Optional.

        Returns:
            The name of the established session (str).

        Raises:
            FileNotFoundError: If the specified avatar file does not exist.
            ConnectionError: If unable to connect to the API.
            TimeoutError: If the API request times out.
            requests.exceptions.RequestException: For other HTTP-related errors.
            json.JSONDecodeError: If the response is not valid JSON.
            ValueError: If the API call fails or returns an invalid status.
        """
        # Prepare form data
        data = {
            'configuration': json.dumps(configuration), # Flask expects a string
        }
        if base_fps is not None:
            data['baseFps'] = str(base_fps) # Flask expects a string
        if live2d_token is not None:
            data['live2Dtoken'] = live2d_token
        if livekit_url is not None:
            data['livekitUrl'] = livekit_url

        try:
            # Open the avatar file in binary read mode
            files = {'avatar': ('avatar.png', avatar, 'image/png')}
            response = self._make_request('POST', 'establish_session', data=data, files=files)
            
            # The Flask app's `Result` function returns the session name in the 'data' field.
            return response['data']
        except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as e:
            # Re-raise exceptions from _make_request or custom ValueError
            raise e 

    def switch_state(self, session_name: str, state: str) -> bool:
        """
        Invokes the /switch_state endpoint to switch the state of a Live2D session.

        This endpoint expects JSON data for the session name and state.
        Args:
            session_name: The name of the session to switch.
            state: The new state to switch to (e.g., 'idle').

        Returns:
            True if the state switch was successful.

        Raises:
            ConnectionError: If unable to connect to the API.
            TimeoutError: If the API request times out.
            requests.exceptions.RequestException: For other HTTP-related errors.
            json.JSONDecodeError: If the response is not valid JSON.
            ValueError: If the API call fails or returns an invalid status.
        """
        # Prepare JSON payload
        payload = {'sessionName': session_name,'state': state}
        response = self._make_request('POST','switch_state', json=payload)
        
        # The Flask app's `Result` function returns status True on success.
        return response['status']

    def shutdown_session(self, session_name: str) -> bool:
        """
        Invokes the /shutdown_session endpoint to terminate a Live2D session.

        This endpoint expects JSON data for the session name.

        Args:
            session_name: The name of the session to shut down.

        Returns:
            True if the session was successfully shut down.

        Raises:
            ConnectionError: If unable to connect to the API.
            TimeoutError: If the API request times out.
            requests.exceptions.RequestException: For other HTTP-related errors.
            json.JSONDecodeError: If the response is not valid JSON.
            ValueError: If the API call fails or returns an invalid status.
        """
        # Prepare JSON payload
        payload = {'sessionName': session_name}
        response = self._make_request('POST', 'shutdown_session', json=payload)
        
        # The Flask app's `Result` function returns status True on success.
        return response['status'] 

    def compile(
        self,
        configuration: typing.Dict[str, typing.Any],
        avatar: bytes,
        base_fps: int
    ) -> bool:
        """
        Invokes the /compile endpoint to compile a Live2D configuration and avatar.

        This endpoint expects form-data for configuration, baseFps,
        and a file upload for the avatar.

        Args:
            configuration: A dictionary representing the Live2D configuration.
            avatar: The bytes of the avatar model.
            base_fps: The base frames per second for compilation.

        Returns:
            True if compilation was successful.

        Raises:
            FileNotFoundError: If the specified avatar file does not exist.
            ConnectionError: If unable to connect to the API.
            TimeoutError: If the API request times out.
            requests.exceptions.RequestException: For other HTTP-related errors.
            json.JSONDecodeError: If the response is not valid JSON.
            ValueError: If the API call fails or returns an invalid status.
        """
        # Prepare form data
        data = {
            'configuration': json.dumps(configuration), # Flask expects a string
            'baseFps': str(base_fps) # Flask expects a string
        }
        
        try:
            # Open the avatar file in binary read mode
            files = {'avatar': ('avatar.png', avatar, 'image/png')}
            response = self._make_request('POST', 'compile', data=data, files=files)
            
            # The Flask app's `Result` function returns status True on success.
            return response['status']
        except (requests.exceptions.RequestException, json.JSONDecodeError, ValueError) as e:
            # Re-raise exceptions from _make_request or custom ValueError
            raise e