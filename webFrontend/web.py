import asyncio
import hashlib
import threading
import uuid
import eventlet.wsgi
import flask
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit
import time
import eventlet
import livekit.api.room_service
import Tha4Api
from AIDubMiddlewareAPI import AIDubMiddlewareAPI
import logger
from webFrontend import characterGenerator
import webFrontend.chatbotManager as chatbotManager
import dataProvider
import config
import webFrontend.chatbotManager
from webFrontend.config import LIVEKIT_API_EXTERNAL_URL
import exceptions
import os
from io import BytesIO
import livekit.api
import taskManager

app = flask.Flask(__name__)
cors = CORS(app)
socket = SocketIO(app, cors_allowed_origins='*', async_mode='gevent')

app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = webFrontend.config.SECRET_KEY
dProvider = dataProvider.DataProvider(f'{config.BLOB_URL}/data.db')
taskManager = taskManager.TaskManager(dProvider)
chatbotManager = chatbotManager.chatbotManager(dProvider)
asyncEventLoop = asyncio.new_event_loop()
asyncio.set_event_loop(asyncEventLoop)


async def getLiveKitAPI():
    return livekit.api.LiveKitAPI(f"https://{webFrontend.config.LIVEKIT_API_EXTERNAL_URL}", webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET)


def Result(status, data):
    return {
        'status': status,
        'data': data
    }


def parseRequestRange(s, flen):
    s = s[s.find('=')+1:]
    c = s.split('-')
    if len(c) != 2:
        return None
    else:
        if c[0] == '' and c[1] == '':
            return [0, flen - 1]
        elif c[1] == '':
            return [int(c[0]), flen - 1]
        elif c[0] == '':
            return [flen - int(c[1]) - 1, flen - 1]
        else:
            return [int(i) for i in c]


def makeFileResponse(file: bytes, mime: str):
    isPreview = not mime.startswith('application')
    if flask.request.headers.get('Range') != None:
        fileLength = len(file)
        reqRange = parseRequestRange(
            flask.request.headers.get('Range'), fileLength)

        response_file = bytes()

        response_file = file[reqRange[0]:reqRange[1]
                             if reqRange[0] != reqRange[1] else reqRange[1] + 1]

        response = flask.make_response(response_file)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Range'] = 'bytes ' + \
            str(reqRange[0]) + '-' + \
            str(reqRange[1]) + '/' + str(fileLength)
        response.headers['Content-Type'] = mime
        if response.headers['Content-Type'].startswith('application'):
            response.headers['Content-Disposition'] = "attachment;"

        response.status_code = 206
        return response

    return flask.send_file(BytesIO(file), as_attachment=not isPreview, mimetype=mime)


def authenticateSession() -> int:
    try:
        return flask.session['user']
    except:
        return -1


@app.after_request
def afterRequst(f):
    dProvider.db.db.commit()
    f.headers.add('Access-Control-Allow-Credentials', 'true')
    return f


@app.route("/api/v1/service/info", methods=["GET"])
def serviceInfo():
    return Result(
        True,
        {
            'initialized': dProvider.checkIfInitialized(),
            'api_ver': 'v2',
            'api_name': 'Frolicking Flames',
            'image_model': config.USE_MODEL_IMAGE_PARSING,
            'chat_model': config.USE_MODEL,
            'authenticated_session': authenticateSession(),
            'session_username': dProvider.getUserName(),
            'user_persona': dProvider.getUserPersona() if authenticateSession() != -1 else '',
            'gpt_sovits_middleware_url': dProvider.getGPTSoVITsMiddleware() if authenticateSession() != -1 else '',
            'tha4_middleware_url': dProvider.getTha4MiddlewareAPI() if authenticateSession() != -1 else '',
        }
    )


@app.route("/api/v1/user/login", methods=["POST"])
def userLogin():
    pwd = ''

    try:
        data = flask.request.get_json()
        pwd = data['password']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    if dProvider.authenticate(pwd):
        flask.session['user'] = int(time.time())
        return Result(True, 'success')
    else:
        return Result(False, 'invalid password')


@app.route("/api/v1/char_list", methods=["POST"])
def charList():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    return Result(True, dProvider.getCharacterList())

@app.route("/api/v1/chat/establish", methods=["POST"])
def chatEstablish():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    session = ''
    charName = flask.request.json.get('charName')
    if charName is None:
        return Result(False, 'invalid form')
    
    session = chatbotManager.createSession(charName)
    return Result(True, {'session': session})


@socket.on('connect', '/chat')
def socketConnect():
    # set client sid
    flask.session['sid'] = flask.request.sid
    logger.Logger.log(f'client {flask.session.get("sid")} connected')


@socket.on('initialize', '/chat')
def socketChatEstablish(data):
    # get client id
    client_sid = flask.session.get('sid', None)
    
    sessionName = data.get('sessionName')
    if sessionName is None:
        logger.Logger.log('invalid session name')
        socket.emit('error', 'invalid session name', room=client_sid, namespace="/chat")
        return
    
    beginMsg = data.get('beginMsg')
    if beginMsg is None:
        logger.Logger.log('invalid begin message')
        socket.emit('error', 'invalid begin message', room=client_sid, namespace="/chat")
        return

    # check if session exist
    session = chatbotManager.getSession(sessionName)
    if session is None:
        socket.emit('error', 'invalid session', room=client_sid, namespace="/chat")
        return
    
    logger.Logger.log(f'session {sessionName} established')
    # bind client id to session
    chatbotManager.bindClient(sessionName, client_sid)
    session.beginChat(beginMsg)
    
@socket.on('message', '/chat')
def socketChatMessage(data):
    # get client id
    client_sid = flask.session.get('sid', None)
    
    session = chatbotManager.getSessionByClient(client_sid)
    session.sendMessage(data['msgChain'])

@app.route("/api/v1/chat/keep_alive", methods=["POST"])
def chatKeepAlive():
    session = ''

    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')
    try:
        data = flask.request.get_json()
        session = data['session']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    chatbotManager.getSession(session)
    return Result(True, 'success')


@app.route("/api/v1/chat/terminate", methods=["POST"])
def chatTerminate():
    session = ''

    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')
    try:
        data = flask.request.get_json()
        session = data['session']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    chatbotManager.terminateSession(session)

    return Result(True, 'success')


@app.route("/api/v1/attachment/upload/audio", methods=["POST"])
def attachmentUploadAudio():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    for i in flask.request.files:
        logger.Logger.log(flask.request.files[i].filename)
        mime = flask.request.files[i].mimetype
        logger.Logger.log(mime)
        if not mime.startswith('audio/'):
            return Result(False, 'invalid mimetype expect `audio/`')
        io = BytesIO()
        flask.request.files[i].save(io)
        io.seek(0)
        id = dProvider.saveAudioAttachment(io.read(), mime)
        return {'data': 'success', 'id': id}


@app.route("/api/v1/attachment/upload/image", methods=["POST"])
def attachmentUploadImage():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    for i in flask.request.files:
        logger.Logger.log(flask.request.files[i].filename)
        mime = flask.request.files[i].mimetype
        if not mime.startswith('image/'):
            return Result(False, 'invalid mimetype expect `image/`')
        io = BytesIO()
        flask.request.files[i].save(io)
        io.seek(0)
        id = dProvider.saveImageAttachment(io.read(), mime)
        # only accept the first file
        return {'data': 'success', 'id': id}


@app.route("/api/v1/attachment/<attachmentId>", methods=["GET"])
def attachmentDownload(attachmentId: str):
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    mime, file = dProvider.getAttachment(attachmentId)
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/<id>/info", methods=["POST"])
def charInfo(id):
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        d = dProvider.getCharacter(int(id))
        if d is None:
            return Result(False, 'character not exist')

        return Result(True, d)
    except ValueError as e:
        return Result(False, f'invalid form: {str(e)}')


@app.route("/api/v1/char/<id>/avatar", methods=["GET"])
def charAvatar(id):
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    mime, file = dProvider.getCharacterAvatar(int(id))
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/<id>/edit", methods=["POST"])
def charEdit(id):
    # offset default to 0
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    charName = ''
    charPrompt = ''
    pastMemories = ''
    exampleChats = ''
    useStickerSet = 0
    useTTSModel = ''
    tha4Service = ''

    try:
        data = flask.request.get_json()
        logger.Logger.log(data)
        charName = data['charName']
        charPrompt = data['charPrompt']
        pastMemories = data['pastMemories']
        exampleChats = data['exampleChats']
        useStickerSet = data['useStickerSet']
        useTTSModel = data['useTTSModel']
        tha4Service = data['tha4Service']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.updateCharacter(
        int(id), charName, useTTSModel, useStickerSet, charPrompt, pastMemories, exampleChats, tha4Service)

    return Result(True, 'success')


@app.route("/api/v1/char/new", methods=["POST"])
def charNew():
    # offset default to 0
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    charName = ''
    charPrompt = ''
    pastMemories = ''
    exampleChats = ''
    useStickerSet = ''
    useTTSModel = ''
    tha4Service = ''

    try:
        data = flask.request.get_json()
        charName = data['charName']
        charPrompt = data['charPrompt']
        pastMemories = data['pastMemories']
        exampleChats = data['exampleChats']
        useStickerSet = data['useStickerSet']
        useTTSModel = data['useTTSModel']
        tha4Service = data['tha4Service']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.createCharacter(
        charName, useTTSModel, useStickerSet, charPrompt, pastMemories, exampleChats, tha4Service)

    return Result(True, 'success')


@app.route("/api/v1/char/<id>/history/<offset>", methods=["POST"])
def charHistory(id, offset):
    # offset default to 0
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    return Result(True, dProvider.fetchChatHistory(int(id), int(offset)))


@app.route("/api/v1/char/<id>/avatar/update", methods=["POST"])
def charAvatarUpdate(id):
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        for i in flask.request.files:
            io = BytesIO()
            flask.request.files[i].save(io)
            io.seek(0)
            b = io.read()
            dProvider.updateCharacterAvatar(
                int(id), (flask.request.files[i].mimetype, b))
            return Result(True, None)

    except Exception as e:
        return Result(False, f'failed: {str(e)}')

    return Result(True, None)


@app.route("/api/v1/avatar", methods=["GET"])
def avatar():
    # offset default to 0
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    mime, avatarBlob = dProvider.getAvatar()
    return makeFileResponse(avatarBlob, mime)


@app.route("/api/v1/sticker/create_set", methods=["POST"])
def stickerAddSet():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setName = ''
    try:
        setName = flask.request.json['setName']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.createStickerSet(setName)
    return Result(True, None)


@app.route("/api/v1/sticker/delete_set", methods=["POST"])
def stickerDeleteSet():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = 0
    try:
        setId = flask.request.json['setId']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.deleteStickerSet(setId)
    return Result(True, None)


@app.route("/api/v1/sticker/add", methods=["POST"])
def stickerAdd():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = ''
    stickerName = ''
    try:
        setId = flask.request.args['setId']
        stickerName = flask.request.args['stickerName']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    try:
        for i in flask.request.files:
            logger.Logger.log(flask.request.files[i])
            file = BytesIO()
            flask.request.files[i].save(file)
            file.seek(0)
            dProvider.addSticker(int(setId), stickerName,
                                 (flask.request.files[i].mimetype, file.read()))
    except Exception as e:
        return Result(False, f'failed: {str(e)}')

    return Result(True, None)


@app.route("/api/v1/sticker/delete", methods=["POST"])
def stickerDelete():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    stickerId = ''
    try:
        stickerId = flask.request.json['stickerId']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.deleteSticker(stickerId)

    return Result(True, None)


@app.route("/api/v1/sticker/get", methods=["GET"])
def stickerGet():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = 0
    stickerName = ''
    try:
        setId = flask.request.args['setId']
        stickerName = flask.request.args['name']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    try:
        mime, blob = dProvider.getSticker(setId, stickerName)
        return makeFileResponse(blob, mime)
    except exceptions.StickerNotFound as e:
        with open(f'./emotionPack/yoimiya/awkward.png', 'rb+') as file:
            b = file.read()
            return makeFileResponse(b, 'image/png')


@app.route("/api/v1/sticker/set_info", methods=["POST"])
def stickerSetInfo():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = 0
    try:
        setId = flask.request.json['setId']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    d = dProvider.getStickerSetInfo(setId)
    if d is None:
        return Result(False, 'sticker set not exist')
    return Result(True, d)


@app.route("/api/v1/sticker/rename_set", methods=["POST"])
def stickerRenameSet():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = 0
    newSetName = ''
    try:
        setId = flask.request.json['setId']
        newSetName = flask.request.json['newSetName']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.renameStickerSet(setId, newSetName)
    return Result(True, None)


@app.route("/api/v1/sticker/set_list", methods=["POST"])
def stickerSetList():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    return Result(True, dProvider.getStickerSetList())


@app.route("/api/v1/sticker/list", methods=["POST"])
def stickerList():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    setId = 0
    try:
        setId = flask.request.json['setId']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    return Result(True, dProvider.getStickerList(setId))


@app.route("/api/v1/tts/service/create", methods=["POST"])
def ttsCreate():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    name = ''
    description = ''
    url = ''
    ttsInferYamlPath = ''

    try:
        name = flask.request.json['name']
        description = flask.request.json['description']
        url = flask.request.json['url']
        ttsInferYamlPath = flask.request.json['ttsInferYamlPath']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.addGPTSoVitsService(name, url, description, ttsInferYamlPath)
    return Result(True, None)


@app.route("/api/v1/tts/ref_audio/add", methods=["POST"])
def ttsRefAudioAdd():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    serviceId = 0
    name = ''
    path = ''
    language = ''
    text = ''
    try:
        serviceId = flask.request.json['serviceId']
        name = flask.request.json['name']
        text = flask.request.json['text']
        path = flask.request.json['path']
        language = flask.request.json['language']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.addGPTSoVitsReferenceAudio(serviceId, name, text, path, language)
    return Result(True, None)


@app.route("/api/v1/tts/ref_audio/delete", methods=["POST"])
def ttsRefAudioDelete():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    id = ''
    try:
        id = flask.request.json['id']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.deleteGPTSoVitsReferenceAudio(id)
    return Result(True, None)


@app.route("/api/v1/tts/service/list", methods=["POST"])
def ttsList():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    return Result(True, dProvider.getGPTSoVitsServices())


@app.route("/api/v1/tts/service/<id>", methods=["POST"])
def ttsService(id):
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        id = int(id)
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    r = dProvider.getGPTSoVitsService(id)
    if r is None:
        return Result(False, 'service not exist')
    else:
        return Result(True, r)


@app.route("/api/v1/tts/service/delete", methods=["POST"])
def ttsServiceDelete():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    id = 0
    try:
        id = int(flask.request.json['id'])
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.deleteGPTSoVitsService(id)
    return Result(True, None)


@app.route("/api/v1/tts/service/update", methods=["POST"])
def ttsServiceUpdate():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    id = 0
    name = ''
    description = ''
    url = ''
    ttsInferYamlPath = ''
    try:
        id = flask.request.json['id']
        name = flask.request.json['name']
        description = flask.request.json['description']
        url = flask.request.json['url']
        ttsInferYamlPath = flask.request.json['ttsInferYamlPath']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    try:
        dProvider.updateGPTSoVitsService(
            id, name, url, description, ttsInferYamlPath)
        return Result(True, None)
    except:
        return Result(False, 'service not exist')


@app.route("/api/v1/stt", methods=["POST"])
def stt():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        for i in flask.request.files:
            path = dProvider.tempFilePathProvider(
                os.path.splitext(flask.request.files[i].filename)[1])
            flask.request.files[i].save(path)
            v = dProvider.parseAudio(path)
            os.remove(path)
            return Result(True, v.strip())

    except Exception as e:
        return Result(False, f'failed: {str(e)}')

    return Result(True, None)


@app.route("/api/v1/avatar/update", methods=["POST"])
def avatarUpdate():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        for i in flask.request.files:
            io = BytesIO()
            flask.request.files[i].save(io)
            io.seek(0)
            b = io.read()
            dProvider.updateAvatar((flask.request.files[i].mimetype, b))
            return Result(True, None)

    except Exception as e:
        return Result(False, f'failed: {str(e)}')

    return Result(True, None)


@app.route("/api/v1/update_username", methods=["POST"])
def updateUsername():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        data = flask.request.get_json()
        userName = data['userName']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.updateUsername(userName)
    return Result(True, 'success')


@app.route("/api/v1/update_persona", methods=["POST"])
def updatePersona():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        data = flask.request.get_json()
        persona = data['persona']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.updateUserPersona(persona)
    return Result(True, 'success')


@app.route("/api/v1/update_password", methods=["POST"])
def updatePassword():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        data = flask.request.get_json()
        password = data['password']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.updatePassword(password)
    return Result(True, 'success')


@app.route("/api/v1/initialize", methods=["POST"])
def initialize():
    if dProvider.checkIfInitialized():
        return Result(False, 'already initialized')

    userName = ''
    password = ''
    try:
        data = flask.request.get_json()
        userName = data['userName']
        password = data['password']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    dProvider.initialize(userName, password)
    flask.session['user'] = int(time.time())
    return Result(True, 'success')


@app.route("/api/v1/rtvc/establish", methods=["POST"])
def establishRealTimeVoiceChat():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    charName = ''
    try:
        data = flask.request.get_json()
        charName = data['charName']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    sessionName = chatbotManager.checkIfRtSessionExist(charName)
    if sessionName is not None:
        logger.Logger.log('Voice chat already exists, terminating old session')
        chatbotManager.terminateRtSession(sessionName)

    sessionName = uuid.uuid4().hex

    session = webFrontend.chatbotManager.VoiceChatSession(
        sessionName, charName, dProvider)
    userName = dProvider.getUserName()

    userToken = livekit.api.AccessToken(
        webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET).with_identity(
        'user').with_name(userName).with_grants(livekit.api.VideoGrants(room_join=True, room=sessionName)).to_jwt()

    botToken = livekit.api.AccessToken(
        webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET).with_identity(
        'model').with_name(charName).with_grants(livekit.api.VideoGrants(room_join=True, room=sessionName)).to_jwt()
        
    live2dToken = livekit.api.AccessToken(
        webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET).with_identity(
        'live2d').with_name(charName).with_grants(livekit.api.VideoGrants(room_join=True, room=sessionName)).to_jwt()

    # livekit api is in this file, so we can't put this logic into createRtSession
    async def f():
        await (await getLiveKitAPI()).room.create_room(create=livekit.api.CreateRoomRequest(name=sessionName, empty_timeout=10*60, max_participants=3))

    asyncEventLoop.run_until_complete(f())

    def th():
        newloop = asyncio.new_event_loop()
        asyncio.set_event_loop(newloop)
        asyncio.ensure_future(session.start(botToken, live2dToken, loop=newloop))
        try:
            newloop.run_forever()
        finally:
            logger.Logger.log('I died')
            newloop.close()

    t = threading.Thread(target=th)
    t.start()

    chatbotManager.createRtSession(charName, sessionName, session)

    return Result(True, {'session': sessionName, 'token': userToken, 'url': webFrontend.config.LIVEKIT_API_EXTERNAL_URL})


@app.route("/api/v1/rtvc/terminate", methods=["POST"])
def terminateRealTimeVoiceChat():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    try:
        data = flask.request.get_json()
        sessionName = data['session']
    except Exception as e:
        return Result(False, f'invalid form: {str(e)}')

    try:
        chatbotManager.terminateRtSession(sessionName)
    except:
        return Result(False, 'invalid session')

    return Result(True, 'success')


@app.route("/api/v1/gpt_sovits_middleware/info", methods=["POST"])
def gptSovitsMiddlewareInfo():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    try:
        return Result(True, taskManager.getInfo())
    except Exception as e:
        return Result(False, f'Middleware not running: {str(e)}')


@app.route("/api/v1/gpt_sovits_middleware/run_training", methods=["POST"])
def gptSovitsMiddlewareRunTraining():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    json_req = flask.request.get_json()
    enabled_char_names = json_req.get('enabled_char_names', [])
    sources_to_fetch = json_req.get('sources_to_fetch', [])

    if not enabled_char_names or not sources_to_fetch:
        return Result(False, 'Invalid request: enabled_char_names and sources_to_fetch are required')

    try:
        return Result(True, taskManager.runAIDubModelTraining(enabled_char_names, sources_to_fetch))
    except Exception as e:
        return Result(False, f'Middleware error: {str(e)}')


@app.route("/api/v1/gpt_sovits_middleware/track", methods=["POST"])
def gptSovitsMiddlewareTrack():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    json_req = flask.request.get_json()
    id = json_req.get('id', None)
    if id is None:
        return Result(False, 'Invalid request: id is required')

    try:
        return Result(True, taskManager.getTaskInfo(id))
    except Exception as e:
        return Result(False, f'Middleware error: {str(e)}')


@app.route("/api/v1/gpt_sovits_middleware/tasks", methods=["POST"])
def gptSovitsMiddlewareTasks():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    try:
        return Result(True, taskManager.getTasks())
    except Exception as e:
        return Result(False, f'Middleware error: {str(e)}')


@app.route("/api/v1/gpt_sovits_middleware/set_url", methods=["POST"])
def gptSovitsMiddlewareSetUrl():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')
    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    try:
        data = flask.request.get_json()
        url = data['url']
        dProvider.setGPTSoVITsMiddleware(url)
        taskManager.updateURL(url)
        return Result(True, 'Middleware URL updated')
    except Exception as e:
        return Result(False, f'Invalid form: {str(e)}')


@app.route("/api/v1/gpt_sovits_middleware/delete_task", methods=["POST"])
def gptSovitsMiddlewareDeleteTask():
    if not authenticateSession():
        return Result(False, 'not authenticated')
    if not dProvider.checkIfInitialized():
        return Result(False, 'not initialized')

    if dProvider.getGPTSoVITsMiddleware() == '':
        return Result(False, 'Middleware not configured')

    try:
        data = flask.request.get_json()
        id = data['id']
        taskManager.deleteTask(id)
        return Result(True, 'Task deleted')
    except Exception as e:
        return Result(False, f'Invalid form: {str(e)}')


@app.route('/api/v1_test/testcase_dub')
def testcaseDub():
    api = AIDubMiddlewareAPI(dProvider.getGPTSoVITsMiddleware())
    # print requests lib path
    r = api.dub('Fireworks are for now, but friends are forever.', 'Yoimiya')
    return flask.Response(r.iter_content(chunk_size=1024), mimetype='audio/aac')


@app.route('/api/v1/extra_info', methods=['POST'])
def extra_info():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')

    return Result(True, dProvider.getExtraInfoList())


@app.route('/api/v1/extra_info/create', methods=['POST'])
def create_extra_info():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'name' not in data or 'description' not in data or 'author' not in data or 'enabled' not in data or 'content' not in data:
        return Result(False, 'Invalid request')
    ei_id = dProvider.createExtraInfo(
        data['name'], data['description'], data['author'], data['content'], data['enabled'])
    return Result(True, ei_id)


@app.route('/api/v1/extra_info/get', methods=['POST'])
def get_extra_info():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    # return Result(True, dProvider.getExtraInfo(data['id']))
    r = dProvider.getExtraInfo(data['id'])
    if r is None:
        return Result(False, 'Invalid id')
    return Result(True, r)


@app.route('/api/v1/extra_info/delete', methods=['POST'])
def delete_extra_info():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    dProvider.deleteExtraInfo(data['id'])
    return Result(True, 'Deleted')


@app.route('/api/v1/extra_info/update', methods=['POST'])
def update_extra_info():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data or 'name' not in data or 'description' not in data or 'author' not in data or 'enabled' not in data or 'content' not in data:
        return Result(False, 'Invalid request')
    dProvider.updateExtraInfo(data['id'], data['name'], data['description'],
                              data['author'], data['content'], data['enabled'])
    return Result(True, 'success')


@app.route('/api/v1/user_script', methods=['POST'])
def user_script():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    return Result(True, dProvider.getUserScriptList())


@app.route('/api/v1/user_script/create', methods=['POST'])
def create_user_script():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'name' not in data or 'content' not in data or 'enabled' not in data or 'author' not in data or 'description' not in data:
        return Result(False, 'Invalid request')
    us_id = dProvider.createUserScript(
        data['name'], data['author'], data['description'], data['content'], data['enabled'])
    return Result(True, us_id)


@app.route('/api/v1/user_script/get', methods=['POST'])
def get_user_script():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    r = dProvider.getUserScript(data['id'])
    if r is None:
        return Result(False, 'Invalid id')
    return Result(True, r)


@app.route('/api/v1/user_script/delete', methods=['POST'])
def delete_user_script():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    dProvider.deleteUserScript(data['id'])
    return Result(True, 'Deleted')


@app.route('/api/v1/user_script/update', methods=['POST'])
def update_user_script():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data or 'name' not in data or 'content' not in data or 'enabled' not in data or 'author' not in data or 'description' not in data:
        return Result(False, 'Invalid request')
    dProvider.updateUserScript(data['id'], data['name'], data['content'],
                               data['author'], data['description'], data['enabled'])
    return Result(True, 'success')


@app.route('/api/v1/tha4_middleware/service/create', methods=['POST'])
def create_tha4_service():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'name' not in data or 'description' not in data or 'configuration' not in data:
        return Result(False, 'Invalid request')
    service_id = dProvider.createTHA4Service(
        data['name'], data['description'], data['configuration'])
    return Result(True, service_id)


@app.route('/api/v1/tha4_middleware/update_url', methods=['POST'])
def update_tha4_middleware_url():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'url' not in data:
        return Result(False, 'Invalid request')
    dProvider.setTHA4Middleware(data['url'])
    return Result(True, 'success')


@app.route('/api/v1/tha4_middleware/service/get', methods=['POST'])
def get_tha4_service():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    r = dProvider.getTHA4Service(data['id'])
    if r is None:
        return Result(False, 'Invalid id')
    del r['avatar']
    return Result(True, r)

@app.route('/api/v1/tha4_middleware/service/delete', methods=['POST'])
def delete_tha4_service():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data:
        return Result(False, 'Invalid request')
    dProvider.deleteTHA4Service(data['id'])
    return Result(True, 'Deleted')

@app.route('/api/v1/tha4_middleware/service/update', methods=['POST'])
def update_tha4_service():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'id' not in data or 'name' not in data or 'description' not in data or 'configuration' not in data:
        return Result(False, 'Invalid request')
    dProvider.updateTHA4Service(data['id'], data['name'], data['description'], data['configuration'])
    return Result(True, 'success')


@app.route('/api/v1/tha4_middleware/service/list', methods=['POST'])
def list_tha4_service():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    return Result(True, dProvider.getTHA4ServiceList())


@app.route('/api/v1/tha4_middleware/service/get_avatar/<int:service_id>', methods=['GET'])
def get_tha4_service_avatar(service_id: int):
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    r = dProvider.getTHA4ServiceAvatar(service_id)
    if r is None:
        return Result(False, 'Invalid id')
    return flask.send_file(BytesIO(r), mimetype='image/png', download_name='avatar.png', as_attachment=True)


@app.route('/api/v1/tha4_middleware/service/set_avatar/<int:service_id>', methods=['POST'])
def set_tha4_service_avatar(service_id: int):
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.files.get('avatar')
    if data is None:
        return Result(False, 'Invalid request')
    dest = BytesIO()
    data.save(dest)
    dProvider.updateTHA4ServiceAvatar(service_id, dest.getvalue())
    return Result(True, 'success')


@app.route('/api/v1/tools/character_generator', methods=['POST'])
def character_generator():
    if authenticateSession() == -1:
        return Result(False, 'Not authenticated')
    data = flask.request.get_json()
    if 'name' not in data:
        return Result(False, 'Invalid request')
    try:
        generator = characterGenerator.CharacterGenerator(dProvider)
        return Result(True, generator.generate(data['name']))
    except Exception as e:
        # return Result(False, f'Error: {str(e)}')
        raise e


def route_message(session: str, message: list[dict[str, str]]) -> None:
    logger.Logger.log(f'Received message from session {session}: {message}')
    
    client = chatbotManager.getClientBySession(session)
    if client is None:
        logger.Logger.log(f'No client found for session {session}')
        return
    
    socket.emit('message', message, namespace='/chat', room=client)



def invoke():
    # eventlet.wsgi.server(eventlet.listen((webFrontend.config.APP_HOST,
    #         webFrontend.config.APP_PORT)), app)
    chatbotManager.on('message', route_message)
    socket.run(app, host=webFrontend.config.APP_HOST,
            port=webFrontend.config.APP_PORT, debug=False)
