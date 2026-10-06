from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from src.api.dependencies import get_workspace
from src.api.schemas.workspace import (Page, MemberRow, MemberDetail, MinistrySummary,
    MinistryRow, MinistryDetail, LeadershipRow, DashboardResponse)
from src.api.v1 import API_PREFIX

router=APIRouter(prefix=API_PREFIX,tags=["Online workspace"])
Workspace=Annotated[object,Depends(get_workspace,scope="function")]
PageNumber=Annotated[int,Query(ge=1,le=100000)]
PageSize=Annotated[int,Query(ge=1,le=100)]
Search=Annotated[str,Query(max_length=200)]
MemberStatus=Literal["ALL","ACTIVE","INACTIVE","TRANSFERRED","DECEASED"]
Sort=Literal["name","member_no","joined_date"]
Direction=Literal["asc","desc"]

@router.get("/members/options",response_model=list[MinistrySummary])
def member_options(service:Workspace):
    return service.member_options()

@router.get("/members",response_model=Page[MemberRow])
def members(service:Workspace,search:Search="",status:MemberStatus="ALL",ministry_id:UUID|None=None,
            page:PageNumber=1,page_size:PageSize=25,sort:Sort="name",direction:Direction="asc"):
    return service.list_members(search,status,ministry_id,page,page_size,sort,direction)

@router.get("/members/{member_id}",response_model=MemberDetail,response_model_exclude_none=True)
def member(service:Workspace,member_id:UUID):
    return service.member_detail(member_id)

@router.get("/media/member-photo/{member_id}")
def photo(service:Workspace,member_id:UUID):
    from src.services.member_photo_service import member_photo
    return Response(member_photo(service.members,member_id),media_type="image/jpeg",
                    headers={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"})

@router.get("/ministries",response_model=Page[MinistryRow])
def ministries(service:Workspace,search:Search="",status:Literal["ALL","ACTIVE","INACTIVE","ARCHIVED"]="ALL",
    category:Literal["ALL","MINISTRY","FELLOWSHIP","DEPARTMENT","UNIT","OTHER"]="ALL",
    page:PageNumber=1,page_size:PageSize=25,ministry_id:UUID|None=None):
    return service.list_ministries(search,status,category,page,page_size,ministry_id)

@router.get("/ministries/{ministry_id}",response_model=MinistryDetail)
def ministry(service:Workspace,ministry_id:UUID):
    return service.ministry_detail(ministry_id)

@router.get("/ministries/{ministry_id}/members",response_model=Page[MemberRow])
def ministry_members(service:Workspace,ministry_id:UUID,search:Search="",status:MemberStatus="ALL",
    page:PageNumber=1,page_size:PageSize=25,sort:Sort="name",direction:Direction="asc"):
    return service.ministry_members(ministry_id,search=search,status=status,page=page,page_size=page_size,sort=sort,direction=direction)

@router.get("/ministries/{ministry_id}/leadership",response_model=Page[LeadershipRow])
def leadership(service:Workspace,ministry_id:UUID,page:PageNumber=1,page_size:PageSize=25):
    return service.leadership(ministry_id,page,page_size)

@router.get("/dashboard",response_model=DashboardResponse)
def dashboard(service:Workspace,ministry_id:UUID|None=None,class_id:UUID|None=None):
    return service.dashboard(ministry_id,class_id)
