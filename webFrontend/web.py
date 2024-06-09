import asyncio
import uuid
import flask
from flask_cors import CORS, cross_origin
import time

import livekit.api.room_service

import webFrontend.chatbotManager as chatbotManager
import dataProvider
import config
import webFrontend.chatbotManager
import webFrontend.config
import exceptions
import os
from io import BytesIO
import livekit.api

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = webFrontend.config.SECRET_KEY
dProvider = dataProvider.DataProvider(f'{config.BLOB_URL}/data.db')
chatbotManager = chatbotManager.chatbotManager(dProvider)
livekitApi = livekit.api.LiveKitAPI(webFrontend.config.LIVEKIT_API_URL, webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET)

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
    return {
        'data': {
            'initialized': dProvider.checkIfInitialized(),
            'api_ver': 'v1',
            'api_name': 'Yoimiya',
            'image_model': config.USE_MODEL_IMAGE_PARSING,
            'chat_model': config.USE_MODEL,
            'authenticated_session': authenticateSession(),
            'session_username': dProvider.getUserName()
        },
        'status': True
    }


@app.route("/api/v1/user/login", methods=["POST"])
def userLogin():
    pwd = ''

    try:
        data = flask.request.get_json()
        pwd = data['password']
    except Exception as e:
        return {'data': 'invalid form', 'status': False}

    if dProvider.authenticate(pwd):
        flask.session['user'] = int(time.time())
        return {'data': 'success', 'status': True}
    else:
        return {'data': 'invalid password', 'status': False}


@app.route("/api/v1/char_list", methods=["POST"])
def charList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {'data': dProvider.getCharacterList(), 'status': True}


@app.route("/api/v1/chat/establish", methods=["POST"])
def chatEstablish():
    charName = ''
    beginMsg = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        charName = data['charName']
        beginMsg = data['msgChain']
    except:
        return {'data': 'invalid form', 'status': False}

    session = chatbotManager.createSession(charName)
    if len(beginMsg) == 1 and beginMsg[0].strip() == '':
        return {'status': False, 'data': 'Null message'}
    return {'response': dProvider.parseMessageChain(beginMsg) + chatbotManager.beginChat(session, beginMsg),
            'session': session,
            'status': True}


@app.route("/api/v1/chat/message", methods=["POST"])
def chatMessage():
    session = ''
    msgChain = []

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
        msgChain = data['msgChain']
    except:
        return {'data': 'invalid form', 'status': False}

    if len(msgChain) == 1 and msgChain[0].strip() == '':
        return {'status': False, 'data': 'Null message'}
    try:
        return {'response': dProvider.parseMessageChain(msgChain) + chatbotManager.sendMessage(session, msgChain),
                'session': session,
                'status': True}
    except exceptions.SessionNotFound as e:
        return {'status': False, 'data': str(e)}


@app.route("/api/v1/chat/keep_alive", methods=["POST"])
def chatKeepAlive():
    session = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
    except Exception as e:
        return {'data': 'invalid form', 'status': False}

    chatbotManager.getSession(session)
    return {'data': 'success', 'status': True}


@app.route("/api/v1/chat/terminate", methods=["POST"])
def chatTerminate():
    session = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
    except:
        return {'data': 'invalid form', 'status': False}

    chatbotManager.terminateSession(session)

    return {'data': 'success', 'status': True}


@app.route("/api/v1/attachment/upload/audio", methods=["POST"])
def attachmentUploadAudio():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    for i in flask.request.files:
        print(flask.request.files[i].filename)
        mime = flask.request.files[i].mimetype
        print(mime)
        if not mime.startswith('audio/'):
            return {'data': 'invalid mimetype expect `audio/`', 'status': False}
        io = BytesIO()
        flask.request.files[i].save(io)
        io.seek(0)
        id = dProvider.saveAudioAttachment(io.read(), mime)
        return {'data': 'success', 'id': id, 'status': True}


@app.route("/api/v1/attachment/upload/image", methods=["POST"])
def attachmentUploadImage():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    for i in flask.request.files:
        print(flask.request.files[i].filename)
        mime = flask.request.files[i].mimetype
        if not mime.startswith('image/'):
            return {'data': 'invalid mimetype expect `image/`', 'status': False}
        io = BytesIO()
        flask.request.files[i].save(io)
        io.seek(0)
        id = dProvider.saveImageAttachment(io.read(), mime)
        # only accept the first file
        return {'data': 'success', 'id': id, 'status': True}


@app.route("/api/v1/attachment/<attachmentId>", methods=["GET"])
def attachmentDownload(attachmentId: str):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    mime, file = dProvider.getAttachment(attachmentId)
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/<id>/info", methods=["POST"])
def charInfo(id):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        d = dProvider.getCharacter(int(id))
        if d is None:
            return {'data': 'character not exist', 'status': False}

        return {'data': d, 'status': True}
    except ValueError:
        return {'data': 'invalid form', 'status': False}


@app.route("/api/v1/char/<id>/avatar", methods=["GET"])
def charAvatar(id):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    mime, file = dProvider.getCharacterAvatar(int(id))
    return makeFileResponse(file, mime)


@app.route("/api/v1/char/<id>/edit", methods=["POST"])
def charEdit(id):
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    charName = ''
    charPrompt = ''
    pastMemories = ''
    exampleChats = ''
    useStickerSet = 0
    useTTSService = 0

    try:
        data = flask.request.get_json()
        print(data)
        charName = data['charName']
        charPrompt = data['charPrompt']
        pastMemories = data['pastMemories']
        exampleChats = data['exampleChats']
        useStickerSet = data['useStickerSet']
        useTTSService = data['useTTSService']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.updateCharacter(
        int(id), charName, useTTSService, useStickerSet, charPrompt, pastMemories, exampleChats)

    return {
        'data': 'success',
        'status': 'true'
    }


@app.route("/api/v1/char/new", methods=["POST"])
def charNew():
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    charName = ''
    charPrompt = ''
    pastMemories = ''
    exampleChats = ''
    useStickerSet = ''
    useTTSService = ''

    try:
        data = flask.request.get_json()
        charName = data['charName']
        charPrompt = data['charPrompt']
        pastMemories = data['pastMemories']
        exampleChats = data['exampleChats']
        useStickerSet = data['useStickerSet']
        useTTSService = data['useTTSService']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.createCharacter(
        charName, useTTSService, useStickerSet, charPrompt, pastMemories, exampleChats)

    return {
        'data': 'success',
        'status': 'true'
    }


@app.route("/api/v1/char/<id>/history/<offset>", methods=["POST"])
def charHistory(id, offset):
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {
        'data': dProvider.fetchChatHistory(int(id), int(offset)),
        'status': True
    }


@app.route("/api/v1/char/<id>/avatar/update", methods=["POST"])
def charAvatarUpdate(id):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        for i in flask.request.files:
            io = BytesIO()
            flask.request.files[i].save(io)
            io.seek(0)
            b = io.read()
            dProvider.updateCharacterAvatar(
                int(id), (flask.request.files[i].mimetype, b))
            return {'status': True}

    except Exception as e:
        return {'status': False, 'data': f'failed: {str(e)}'}

    return {'status': True}


@app.route("/api/v1/avatar", methods=["GET"])
def avatar():
    # offset default to 0
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    mime, avatarBlob = dProvider.getAvatar()
    return makeFileResponse(avatarBlob, mime)


@app.route("/api/v1/sticker/create_set", methods=["POST"])
def stickerAddSet():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setName = ''
    try:
        setName = flask.request.json['setName']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.createStickerSet(setName)
    return {'status': True}


@app.route("/api/v1/sticker/delete_set", methods=["POST"])
def stickerDeleteSet():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = 0
    try:
        setId = flask.request.json['setId']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.deleteStickerSet(setId)
    return {'status': True}


@app.route("/api/v1/sticker/add", methods=["POST"])
def stickerAdd():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = ''
    stickerName = ''
    try:
        setId = flask.request.args['setId']
        stickerName = flask.request.args['stickerName']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    try:
        for i in flask.request.files:
            print(flask.request.files[i])
            file = BytesIO()
            flask.request.files[i].save(file)
            file.seek(0)
            dProvider.addSticker(int(setId), stickerName,
                                 (flask.request.files[i].mimetype, file.read()))
    except Exception as e:
        return {'status': False, 'data': f'failed: {str(e)}'}

    return {'status': True}


@app.route("/api/v1/sticker/delete", methods=["POST"])
def stickerDelete():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    stickerId = ''
    try:
        stickerId = flask.request.json['stickerId']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.deleteSticker(stickerId)

    return {'status': True}


@app.route("/api/v1/sticker/get", methods=["GET"])
def stickerGet():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = 0
    stickerName = ''
    try:
        setId = flask.request.args['setId']
        stickerName = flask.request.args['name']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

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
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = 0
    try:
        setId = flask.request.json['setId']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    d = dProvider.getStickerSetInfo(setId)
    if d is None:
        return {'data': 'sticker set not exist', 'status': False}
    return {'data': d, 'status': True}


@app.route("/api/v1/sticker/rename_set", methods=["POST"])
def stickerRenameSet():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = 0
    newSetName = ''
    try:
        setId = flask.request.json['setId']
        newSetName = flask.request.json['newSetName']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.renameStickerSet(setId, newSetName)
    return {'status': True}


@app.route("/api/v1/sticker/set_list", methods=["POST"])
def stickerSetList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {
        'data': dProvider.getStickerSetList(),
        'status': True
    }


@app.route("/api/v1/sticker/list", methods=["POST"])
def stickerList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    setId = 0
    try:
        setId = flask.request.json['setId']
    except:
        return {'status': False, 'data': 'invalid form'}

    return {
        'data': dProvider.getStickerList(setId),
        'status': True
    }


@app.route("/api/v1/tts/service/create", methods=["POST"])
def ttsCreate():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    name = ''
    description = ''
    url = ''
    try:
        name = flask.request.json['name']
        description = flask.request.json['description']
        url = flask.request.json['url']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.addGPTSoVitsService(name, url, description)
    return {'status': True}


@app.route("/api/v1/tts/ref_audio/add", methods=["POST"])
def ttsRefAudioAdd():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

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
        return {'status': False, 'data': 'invalid form'}

    dProvider.addGPTSoVitsReferenceAudio(serviceId, name, text, path, language)
    return {'status': True}


@app.route("/api/v1/tts/ref_audio/delete", methods=["POST"])
def ttsRefAudioDelete():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    id = ''
    try:
        id = flask.request.json['id']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.deleteGPTSoVitsReferenceAudio(id)
    return {'status': True}


@app.route("/api/v1/tts/service/list", methods=["POST"])
def ttsList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {
        'data': dProvider.getGPTSoVitsServices(),
        'status': True
    }


@app.route("/api/v1/tts/service/<id>", methods=["POST"])
def ttsService(id):
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        id = int(id)
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    r = dProvider.getGPTSoVitsService(id)
    if r is None:
        return {'data': 'service not exist', 'status': False}
    else:
        return {'data': r, 'status': True}


@app.route("/api/v1/tts/service/delete", methods=["POST"])
def ttsServiceDelete():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    id = 0
    try:
        id = int(flask.request.json['id'])
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    dProvider.deleteGPTSoVitsService(id)
    return {'status': True}


@app.route("/api/v1/tts/service/update", methods=["POST"])
def ttsServiceUpdate():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    id = 0
    name = ''
    description = ''
    url = ''
    try:
        id = flask.request.json['id']
        name = flask.request.json['name']
        description = flask.request.json['description']
        url = flask.request.json['url']
    except Exception as e:
        return {'status': False, 'data': 'invalid form'}

    try:
        dProvider.updateGPTSoVitsService(id, name, url, description)
        return {'status': True}
    except:
        return {'status': False, 'data': 'service not exist'}


@app.route("/api/v1/stt", methods=["POST"])
def stt():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        for i in flask.request.files:
            path = dProvider.tempFilePathProvider(
                os.path.splitext(flask.request.files[i].filename)[1])
            flask.request.files[i].save(path)
            v = dProvider.parseAudio(path)
            os.remove(path)
            return {'status': True, 'data': v.strip()}

    except Exception as e:
        return {'status': False, 'data': f'failed: {str(e)}'}

    return {'status': True}


@app.route("/api/v1/avatar/update", methods=["POST"])
def avatarUpdate():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        for i in flask.request.files:
            io = BytesIO()
            flask.request.files[i].save(io)
            io.seek(0)
            b = io.read()
            dProvider.updateAvatar((flask.request.files[i].mimetype, b))
            return {'status': True}

    except Exception as e:
        return {'status': False, 'data': f'failed: {str(e)}'}

    return {'status': True}


@app.route("/api/v1/update_username", methods=["POST"])
def updateUsername():
    if not authenticateSession():
        return {'data': 'not authenticated', ' status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        data = flask.request.get_json()
        userName = data['userName']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.updateUsername(userName)
    return {'data': 'success', 'status': True}


@app.route("/api/v1/update_password", methods=["POST"])
def updatePassword():
    if not authenticateSession():
        return {'data': 'not authenticated', ' status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    try:
        data = flask.request.get_json()
        password = data['password']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.updatePassword(password)
    return {'data': 'success', 'status': True}



@app.route("/api/v1/initialize", methods=["POST"])
def initialize():
    if dProvider.checkIfInitialized():
        return {'data': 'already initialized', 'status': False}

    userName = ''
    password = ''
    try:
        data = flask.request.get_json()
        userName = data['userName']
        password = data['password']
    except:
        return {'data': 'invalid form', 'status': False}

    dProvider.initialize(userName, password)
    flask.session['user'] = int(time.time())
    return {'data': 'success', 'status': True}


@app.route("/api/v1/rtvc/establish", methods=["POST"])
def establishRealTimeVoiceChat():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    charName = ''
    try:
        data = flask.request.get_json()
        charName = data['charName']
    except:
        return {'data': 'invalid form', 'status': False}
    
    sessionName = uuid.uuid4().hex
    session = webFrontend.chatbotManager.VoiceChatSession(sessionName, charName, dProvider)
    userName = dProvider.getUserName()
    
    userToken = livekit.api.AccessToken(
            webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET).with_identity(
                'user').with_name(userName).with_grants(livekit.api.VideoGrants(room_join=True, room=sessionName)).to_jwt()
            
    botToken = livekit.api.AccessToken(
            webFrontend.config.LIVEKIT_API_KEY, webFrontend.config.LIVEKIT_API_SECRET).with_identity(
                'model').with_name(charName).with_grants(livekit.api.VideoGrants(room_join=True, room=sessionName)).to_jwt()
    
    async def r():
        # livekit api is in this file, so we can't put this logic into createRtSession
        await livekitApi.room.create_room(livekit.api.CreateRoomRequest(sessionName, 10*60, max_participants=2))
        session.start(botToken)
        
    asyncio.get_event_loop().run_until_complete(r())
    
    chatbotManager.createRtSession(charName, sessionName, session)
    
    return {'data': {'session': sessionName, 'token': userToken, 'url': webFrontend.config.LIVEKIT_API_EXTERNAL_URL},'status': True}


def invoke():
    app.run(webFrontend.config.APP_HOST,
            webFrontend.config.APP_PORT, debug=False)
