from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from firebase_admin import auth, firestore, storage
from initialize_firebase import db
from pydantic import BaseModel
from keras.applications import ResNet50
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet import preprocess_input, decode_predictions
import numpy as np
import os
from datetime import datetime

router = APIRouter()
db = firestore.client()
bucket = storage.bucket()
model = ResNet50(weights='imagenet')

class ImagesRead(BaseModel):
    id: str
    uid: str
    filename: str
    image_url: str
    uploaded_at: str
    predictions: dict


@router.post("/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    try:
        token = request.cookies.get("Token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")
        
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        contents = await file.read()

        with open(file.filename, "wb") as f:
            f.write(contents)

        img = image.load_img(file.filename, target_size=(224, 224))
        x = image.img_to_array(img)
        x = np.expand_dims(x, axis=0)
        x = preprocess_input(x)

        preds = model.predict(x)
        results = decode_predictions(preds, top=3)[0]
        json_results = {pred[1]: float(pred[2]) for pred in results}

        blob = bucket.blob(f"uploaded-images/{file.filename}")
        blob.upload_from_filename(file.filename)
        blob.make_public()

        public_url = blob.public_url

        image_id = db.collection('images').document().id

        image_data = {
            'id': image_id,
            'image_url': public_url,
            'uploaded_at': datetime.utcnow(),
            'uid': uid,
            'filename': file.filename,
            'predictions': json_results
        }

        db.collection('images').document(image_id).set(image_data)

        return JSONResponse(content={
            "predictions": json_results,
            "image_url": public_url,
            "uploaded_at": image_data['uploaded_at'].isoformat(),
            "uid": uid,
            "id": image_id
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

    finally:
        if os.path.exists(file.filename):
            os.remove(file.filename)


@router.get("/images", response_model=list[ImagesRead])
async def get_images(request: Request):
    try:
        token = request.cookies.get("Token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")
        
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        images = db.collection('images').where('uid', '==', uid).stream()
        
        image_data = []
        for image in images:
            img_dict = image.to_dict()
            if 'uploaded_at' in img_dict and isinstance(img_dict['uploaded_at'], datetime):
                img_dict['uploaded_at'] = img_dict['uploaded_at'].isoformat()
            image_data.append(img_dict)

        return JSONResponse(content=image_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching images: {str(e)}")

@router.get("/image/{image_id}", response_model=ImagesRead)
async def get_image(request: Request, image_id: str):
    try:
        token = request.cookies.get("Token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")
        
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        image_ref = db.collection('images').where('id', '==', image_id).where('uid', '==', uid).stream()
        image_docs = list(image_ref) 

        if not image_docs: 
            raise HTTPException(status_code=404, detail="Image not found")

        for doc in image_docs:
            image_data = doc.to_dict()
            if 'uploaded_at' in image_data and isinstance(image_data['uploaded_at'], datetime):
                image_data['uploaded_at'] = image_data['uploaded_at'].isoformat()
            return JSONResponse(content=image_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching image: {str(e)}")
    

@router.delete("/delete-image/{image_id}")
async def delete_image(request: Request, image_id: str):
    try:
        token = request.cookies.get("Token")
        
        if not token:
            raise HTTPException(status_code=401, detail="Token not found")
        
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")

        image_ref = db.collection('images').where('id', '==', image_id).where('uid', '==', uid).stream()
        image_docs = list(image_ref) 

        if not image_docs: 
            raise HTTPException(status_code=404, detail="Image not found")

        for doc in image_docs:
            doc.reference.delete()

        return {"message": "Image deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting image: {str(e)}")
