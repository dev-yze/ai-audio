import json

# api 返回数据
class ApiResponse():

    def __init__(self, code, msg, data) -> None:
        self.code = code
        self.msg = msg
        self.data = data

    def to_json(self):
        response_dict = {
            'code': self.code,
            'msg': self.msg,
            'data': self.data
        }
        return json.dumps(response_dict)