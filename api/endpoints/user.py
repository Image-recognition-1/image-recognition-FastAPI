from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from firebase_admin import auth, firestore, storage
from pydantic import BaseModel
from initialize_firebase import db
import uuid
import mimetypes


router = APIRouter()
db = firestore.client()

class UserRead(BaseModel):
    uid: str
    email: str
    fullName: str
    username: str
    role: str
    disabled: bool
    profilePictureUrl: str = None

class UpdateUserRequest(BaseModel):
    email: str = None
    fullName: str = None
    username: str = None
    role: str = None
    disabled: bool = None
    profilePictureUrl: str = None


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
            "disabled": user_data["disabled"],
            "profilePictureUrl": user_data["profilePictureUrl"]
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
async def update_user(uid: str, user_update: UpdateUserRequest):
    user_ref = db.collection('users').document(uid)
    user = user_ref.get()

    if not user.exists:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.dict(exclude_unset=True)
    if update_data:
        user_ref.update(update_data)
        return UserRead(**user_ref.get().to_dict())
    else:
        raise HTTPException(status_code=400, detail="No data to update")
    

@router.put("/update-profile-picture/{uid}", response_model=UserRead)
async def update_profile_picture(uid: str, file: UploadFile = File(...)):
    try:
        file_extension = mimetypes.guess_extension(file.content_type)
        if not file_extension:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        file_name = f"profile-pictures/{uuid.uuid4()}{file_extension}"

        bucket = storage.bucket()
        blob = bucket.blob(file_name)
        blob.upload_from_file(file.file, content_type=file.content_type)
        
        blob.make_public()
        profile_picture_url = blob.public_url

        user_ref = db.collection("users").document(uid)
        user = user_ref.get()

        if not user.exists:
            raise HTTPException(status_code=404, detail="User not found")

        user_ref.update({
            "profilePictureUrl": profile_picture_url
        })

        updated_user = user_ref.get().to_dict()
        updated_user["uid"] = uid

        return UserRead(**updated_user)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))