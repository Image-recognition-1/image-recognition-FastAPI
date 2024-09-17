from fastapi import APIRouter, HTTPException, Request
from firebase_admin import auth, firestore
from pydantic import BaseModel
from initialize_firebase import db


router = APIRouter()
db = firestore.client()

class UserRead(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    role: str
    disabled: bool

class UpdateUserRequest(BaseModel):
    email: str = None
    fullName: str = None
    username: str = None
    role: str = None
    disabled: bool = None


@router.get("/getme", response_model=UserRead)
async def get_me(request: Request):
    try:
        token = request.cookies.get("Token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")
        
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_ref = db.collection('users').document(uid)
        user_snapshot = user_ref.get(timeout=10)

        if not user_snapshot.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_snapshot.to_dict()

        return {
            "uid": user_data["uid"],
            "email": user_data["email"],
            "fullName": user_data["fullName"],
            "username": user_data["username"],
            "role": user_data["role"],
            "disabled": user_data["disabled"]
        }

    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired")

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Error verifying token")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching user data: {str(e)}")



@router.put("/update-user/{uid}", response_model=UserRead)
async def update_user(uid: str, update_request: UpdateUserRequest):
    try:
        user_ref = db.collection('users').document(uid)
        user_snapshot = user_ref.get()

        if not user_snapshot.exists():
            raise HTTPException(status_code=404, detail="User not found")

        update_data = {}

        if update_request.email:
            auth.update_user(uid, email=update_request.email)
            update_data['email'] = update_request.email
        
        if update_request.fullName:
            auth.update_user(uid, display_name=update_request.fullName)
            update_data['fullName'] = update_request.fullName

        if update_request.username:
            update_data['username'] = update_request.username

        if update_request.role:
            update_data['role'] = update_request.role

        if update_request.disabled is not None:
            auth.update_user(uid, disabled=update_request.disabled)
            update_data['disabled'] = update_request.disabled

        if update_data:
            user_ref.update(update_data)

        updated_user_snapshot = user_ref.get()
        updated_user_data = updated_user_snapshot.to_dict()

        return UserRead(**updated_user_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating user: {str(e)}")
