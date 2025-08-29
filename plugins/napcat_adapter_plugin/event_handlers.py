
from src.plugin_system import BaseEventHandler
from src.plugin_system.base.base_event import HandlerResult

from .src.send_handler import send_handler
from .event_types import *

from src.common.logger import get_logger
logger = get_logger("napcat_adapter")


class SetProfileHandler(BaseEventHandler):
    handler_name: str = "napcat_set_qq_profile_handler"
    handler_description: str = "设置账号信息"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_PROFILE]

    async def execute(self,params:dict):
        raw = params.get("raw",{})
        nickname = params.get("nickname","")
        personal_note = params.get("personal_note","")
        sex = params.get("sex","")

        if params.get("raw",""):
            nickname = raw.get("nickname","")
            personal_note = raw.get("personal_note","")
            sex = raw.get("sex","")
        
        if not nickname:
            logger.error("事件 napcat_set_qq_profile 缺少必要参数: nickname ")
            return HandlerResult(False,False,{"status":"error"})

        payload = {
            "nickname": nickname,
            "personal_note": personal_note,
            "sex": sex
            }
        response = await send_handler.send_message_to_napcat(action="set_qq_profile",params=payload)
        if response.get("status","") == "ok":
            if response.get("data","").get("result","") == 0:
                return HandlerResult(True,True,response)
            else:
                logger.error(f"事件 napcat_set_qq_profile 请求失败！err={response.get("data","").get("errMsg","")}")
                return HandlerResult(False,False,response)
        else:
            logger.error("事件 napcat_set_qq_profile 请求失败！")
            return HandlerResult(False,False,{"status":"error"})


class GetOnlineClientsHandler(BaseEventHandler):
    handler_name: str = "napcat_get_online_clients_handler"
    handler_description: str = "获取当前账号在线客户端列表"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_ONLINE_CLIENTS]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        no_cache = params.get("no_cache", False)

        if params.get("raw", ""):
            no_cache = raw.get("no_cache", False)

        payload = {
            "no_cache": no_cache
        }
        response = await send_handler.send_message_to_napcat(action="get_online_clients", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_online_clients 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SetOnlineStatusHandler(BaseEventHandler):
    handler_name: str = "napcat_set_online_status_handler"
    handler_description: str = "设置在线状态"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_ONLINE_STATUS]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        status = params.get("status", "")
        ext_status = params.get("ext_status", "0")
        battery_status = params.get("battery_status", "0")

        if params.get("raw", ""):
            status = raw.get("status", "")
            ext_status = raw.get("ext_status", "0")
            battery_status = raw.get("battery_status", "0")

        if not status:
            logger.error("事件 napcat_set_online_status 缺少必要参数: status")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "status": status,
            "ext_status": ext_status,
            "battery_status": battery_status
        }
        response = await send_handler.send_message_to_napcat(action="set_online_status", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_set_online_status 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetFriendsWithCategoryHandler(BaseEventHandler):
    handler_name: str = "napcat_get_friends_with_category_handler"
    handler_description: str = "获取好友分组列表"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_FRIENDS_WITH_CATEGORY]

    async def execute(self, params: dict):
        payload = {}
        response = await send_handler.send_message_to_napcat(action="get_friends_with_category", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_friends_with_category 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SetAvatarHandler(BaseEventHandler):
    handler_name: str = "napcat_set_qq_avatar_handler"
    handler_description: str = "设置头像"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_AVATAR]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        file = params.get("file", "")

        if params.get("raw", ""):
            file = raw.get("file", "")

        if not file:
            logger.error("事件 napcat_set_qq_avatar 缺少必要参数: file")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "file": file
        }
        response = await send_handler.send_message_to_napcat(action="set_qq_avatar", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_set_qq_avatar 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SendLikeHandler(BaseEventHandler):
    handler_name: str = "napcat_send_like_handler"
    handler_description: str = "点赞"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SEND_LIKE]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        user_id = params.get("user_id", "")
        times = params.get("times", 1)

        if params.get("raw", ""):
            user_id = raw.get("user_id", "")
            times = raw.get("times", 1)

        if not user_id:
            logger.error("事件 napcat_send_like 缺少必要参数: user_id")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "user_id": str(user_id),
            "times": times
        }
        response = await send_handler.send_message_to_napcat(action="send_like", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_send_like 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SetFriendAddRequestHandler(BaseEventHandler):
    handler_name: str = "napcat_set_friend_add_request_handler"
    handler_description: str = "处理好友请求"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_FRIEND_ADD_REQUEST]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        flag = params.get("flag", "")
        approve = params.get("approve", True)
        remark = params.get("remark", "")

        if params.get("raw", ""):
            flag = raw.get("flag", "")
            approve = raw.get("approve", True)
            remark = raw.get("remark", "")

        if not flag or approve is None or remark is None:
            logger.error("事件 napcat_set_friend_add_request 缺少必要参数")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "flag": flag,
            "approve": approve,
            "remark": remark
        }
        response = await send_handler.send_message_to_napcat(action="set_friend_add_request", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_set_friend_add_request 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SetSelfLongnickHandler(BaseEventHandler):
    handler_name: str = "napcat_set_self_longnick_handler"
    handler_description: str = "设置个性签名"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_SELF_LONGNICK]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        longNick = params.get("longNick", "")

        if params.get("raw", ""):
            longNick = raw.get("longNick", "")

        if not longNick:
            logger.error("事件 napcat_set_self_longnick 缺少必要参数: longNick")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "longNick": longNick
        }
        response = await send_handler.send_message_to_napcat(action="set_self_longnick", params=payload)
        if response.get("status", "") == "ok":
            if response.get("data", {}).get("result", "") == 0:
                return HandlerResult(True, True, response)
            else:
                logger.error(f"事件 napcat_set_self_longnick 请求失败！err={response.get('data', {}).get('errMsg', '')}")
                return HandlerResult(False, False, response)
        else:
            logger.error("事件 napcat_set_self_longnick 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetLoginInfoHandler(BaseEventHandler):
    handler_name: str = "napcat_get_login_info_handler"
    handler_description: str = "获取登录号信息"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_LOGIN_INFO]

    async def execute(self, params: dict):
        payload = {}
        response = await send_handler.send_message_to_napcat(action="get_login_info", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_login_info 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetRecentContactHandler(BaseEventHandler):
    handler_name: str = "napcat_get_recent_contact_handler"
    handler_description: str = "最近消息列表"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_RECENT_CONTACT]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        count = params.get("count", 20)

        if params.get("raw", ""):
            count = raw.get("count", 20)

        payload = {
            "count": count
        }
        response = await send_handler.send_message_to_napcat(action="get_recent_contact", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_recent_contact 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetStrangerInfoHandler(BaseEventHandler):
    handler_name: str = "napcat_get_stranger_info_handler"
    handler_description: str = "获取(指定)账号信息"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_STRANGER_INFO]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        user_id = params.get("user_id", "")

        if params.get("raw", ""):
            user_id = raw.get("user_id", "")

        if not user_id:
            logger.error("事件 napcat_get_stranger_info 缺少必要参数: user_id")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "user_id": str(user_id)
        }
        response = await send_handler.send_message_to_napcat(action="get_stranger_info", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_stranger_info 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetFriendListHandler(BaseEventHandler):
    handler_name: str = "napcat_get_friend_list_handler"
    handler_description: str = "获取好友列表"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_FRIEND_LIST]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        no_cache = params.get("no_cache", False)

        if params.get("raw", ""):
            no_cache = raw.get("no_cache", False)

        payload = {
            "no_cache": no_cache
        }
        response = await send_handler.send_message_to_napcat(action="get_friend_list", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_friend_list 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetProfileLikeHandler(BaseEventHandler):
    handler_name: str = "napcat_get_profile_like_handler"
    handler_description: str = "获取点赞列表"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_PROFILE_LIKE]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        user_id = params.get("user_id", "")
        start = params.get("start", 0)
        count = params.get("count", 10)

        if params.get("raw", ""):
            user_id = raw.get("user_id", "")
            start = raw.get("start", 0)
            count = raw.get("count", 10)

        payload = {
            "start": start,
            "count": count
        }
        if user_id:
            payload["user_id"] = str(user_id)

        response = await send_handler.send_message_to_napcat(action="get_profile_like", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_profile_like 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class DeleteFriendHandler(BaseEventHandler):
    handler_name: str = "napcat_delete_friend_handler"
    handler_description: str = "删除好友"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.DELETE_FRIEND]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        user_id = params.get("user_id", "")
        temp_block = params.get("temp_block", False)
        temp_both_del = params.get("temp_both_del", False)

        if params.get("raw", ""):
            user_id = raw.get("user_id", "")
            temp_block = raw.get("temp_block", False)
            temp_both_del = raw.get("temp_both_del", False)

        if not user_id or temp_block is None or temp_both_del is None:
            logger.error("事件 napcat_delete_friend 缺少必要参数")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "user_id": str(user_id),
            "temp_block": temp_block,
            "temp_both_del": temp_both_del
        }
        response = await send_handler.send_message_to_napcat(action="delete_friend", params=payload)
        if response.get("status", "") == "ok":
            if response.get("data", {}).get("result", "") == 0:
                return HandlerResult(True, True, response)
            else:
                logger.error(f"事件 napcat_delete_friend 请求失败！err={response.get('data', {}).get('errMsg', '')}")
                return HandlerResult(False, False, response)
        else:
            logger.error("事件 napcat_delete_friend 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetUserStatusHandler(BaseEventHandler):
    handler_name: str = "napcat_get_user_status_handler"
    handler_description: str = "获取(指定)用户状态"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_USER_STATUS]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        user_id = params.get("user_id", "")

        if params.get("raw", ""):
            user_id = raw.get("user_id", "")

        if not user_id:
            logger.error("事件 napcat_get_user_status 缺少必要参数: user_id")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "user_id": str(user_id)
        }
        response = await send_handler.send_message_to_napcat(action="get_user_status", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_user_status 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetStatusHandler(BaseEventHandler):
    handler_name: str = "napcat_get_status_handler"
    handler_description: str = "获取状态"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_STATUS]

    async def execute(self, params: dict):
        payload = {}
        response = await send_handler.send_message_to_napcat(action="get_status", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_status 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class GetMiniAppArkHandler(BaseEventHandler):
    handler_name: str = "napcat_get_mini_app_ark_handler"
    handler_description: str = "获取小程序卡片"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.GET_MINI_APP_ARK]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        type = params.get("type", "")
        title = params.get("title", "")
        desc = params.get("desc", "")
        picUrl = params.get("picUrl", "")
        jumpUrl = params.get("jumpUrl", "")
        webUrl = params.get("webUrl", "")
        rawArkData = params.get("rawArkData", False)

        if params.get("raw", ""):
            type = raw.get("type", "")
            title = raw.get("title", "")
            desc = raw.get("desc", "")
            picUrl = raw.get("picUrl", "")
            jumpUrl = raw.get("jumpUrl", "")
            webUrl = raw.get("webUrl", "")
            rawArkData = raw.get("rawArkData", False)

        if not type or not title or not desc or not picUrl or not jumpUrl:
            logger.error("事件 napcat_get_mini_app_ark 缺少必要参数")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "type": type,
            "title": title,
            "desc": desc,
            "picUrl": picUrl,
            "jumpUrl": jumpUrl,
            "webUrl": webUrl,
            "rawArkData": rawArkData
        }
        response = await send_handler.send_message_to_napcat(action="get_mini_app_ark", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_get_mini_app_ark 请求失败！")
            return HandlerResult(False, False, {"status": "error"})


class SetDiyOnlineStatusHandler(BaseEventHandler):
    handler_name: str = "napcat_set_diy_online_status_handler"
    handler_description: str = "设置自定义在线状态"
    weight: int = 100
    intercept_message: bool = False
    init_subscribe = [NapcatEvent.ACCOUNT.SET_DIY_ONLINE_STATUS]

    async def execute(self, params: dict):
        raw = params.get("raw", {})
        face_id = params.get("face_id", "")
        face_type = params.get("face_type", "0")
        wording = params.get("wording", "")

        if params.get("raw", ""):
            face_id = raw.get("face_id", "")
            face_type = raw.get("face_type", "0")
            wording = raw.get("wording", "")

        if not face_id:
            logger.error("事件 napcat_set_diy_online_status 缺少必要参数: face_id")
            return HandlerResult(False, False, {"status": "error"})

        payload = {
            "face_id": str(face_id),
            "face_type": str(face_type),
            "wording": wording
        }
        response = await send_handler.send_message_to_napcat(action="set_diy_online_status", params=payload)
        if response.get("status", "") == "ok":
            return HandlerResult(True, True, response)
        else:
            logger.error("事件 napcat_set_diy_online_status 请求失败！")
            return HandlerResult(False, False, {"status": "error"})
