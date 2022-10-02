''' Main '''
import hashlib
import logging
from typing import Optional

from fastapi import Depends, FastAPI, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from api.apistructs.members import MembersInfo, MembersOut, MembersTeams
from api.routers import members, projects, user
from module.api_token import APIToken
from module.team import Team
from module.users import User

logging.basicConfig(
    filename='./log/api.log',
    format='%(asctime)s [%(levelname)-5.5s][%(thread)6.6s] [%(module)s:%(funcName)s#%(lineno)d]: %(message)s',  # pylint: disable=line-too-long
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG)

DOC_DESC = '''The more details about how to use this API, please refer to
[API Intro](https://volunteer.coscup.org/docs/dev/api/).'''

TAGS_META = [
    {
        'name': 'user',
        'description': 'More about user self info.',
    },
    {
        'name': 'projects',
        'description': 'List all projects.'
    },
    {
        'name': 'members',
        'description': 'List all members.'
    },
    {
        'name': 'docs',
        'description': 'redirect to docs.',
    },
    {
        'name': 'login',
        'description': 'oauth, login.',
    }
]

app = FastAPI(
    title='Volunteer API.',
    description=DOC_DESC,
    version='2022.10.09',
    openapi_tags=TAGS_META,
    root_path="/api",
    contact={'name': 'Volunteer Team',
             'url': 'https://volunteer.coscup.org/',
             'email': 'volunteer@coscup.org',
             },
    license_info={'name': 'AGPL-3.0',
                  'url': 'https://github.com/COSCUP/COSCUP-Volunteer/blob/master/LICENSE.txt',
                  },
)

app.include_router(members.router)
app.include_router(projects.router)
app.include_router(user.router)


class Token(BaseModel):
    ''' Token '''
    access_token: str
    token_type: str = Field(default='bearer')


@app.get('/', tags=['docs', ],
         summary='API main page.',
         response_class=RedirectResponse, status_code=302)
async def index() -> Optional[str]:
    '''Main page '''
    return f'{app.root_path}{app.docs_url}'


@app.post('/token', tags=['login', ],
          response_model=Token)
async def exchange_access_token(
        form_data: OAuth2PasswordRequestForm = Depends()) -> Token | JSONResponse:
    ''' Exchange access token

    Get your **one-time** use `username`, `password` from volenteer
    [personal setting](/setting/api_token) page to exchanging the API access token.

    '''
    verified_uid = APIToken.verify(
        username=form_data.username, password=form_data.password)

    if verified_uid is not None:
        token = APIToken.create_token(uid=verified_uid)
        return Token(access_token=token)

    return JSONResponse(content={}, status_code=status.HTTP_406_NOT_ACCEPTABLE)


@app.get('/members', tags=['members', ],
         summary='Get members (deprecated).',
         responses={status.HTTP_404_NOT_FOUND: {
             'description': 'Project not found'}},
         response_model=MembersOut,
         deprecated=True,
         )
async def members_past(
        pid: str = Query(description='Project ID.', example='2022')) -> MembersOut | JSONResponse:
    ''' Get Project's members

        **Warning: will be deprecated.**

    '''
    result = MembersOut()
    for team in Team.list_by_pid(pid=pid):
        data = {}
        data['name'] = team['name']
        data['tid'] = team['tid']

        data['chiefs'] = []
        chiefs_infos = User.get_info(uids=team['chiefs'])
        for uid in team['chiefs']:
            if uid not in chiefs_infos:
                continue

            _user = chiefs_infos[uid]
            h_msg = hashlib.md5()
            h_msg.update(_user['oauth']['email'].encode('utf-8'))
            data['chiefs'].append(MembersInfo.parse_obj({
                'name': _user['profile']['badge_name'],
                'email_hash': h_msg.hexdigest(),
            }))

        data['members'] = []
        for _user in User.get_info(uids=list(set(team['members']) - set(team['chiefs']))).values():
            h_msg = hashlib.md5()
            h_msg.update(_user['oauth']['email'].encode('utf-8'))
            data['members'].append(MembersInfo.parse_obj({
                'name': _user['profile']['badge_name'],
                'email_hash': h_msg.hexdigest(),
            }))

        result.data.append(MembersTeams.parse_obj(data))

    if result.data:
        return result

    return JSONResponse(content={}, status_code=status.HTTP_404_NOT_FOUND)
