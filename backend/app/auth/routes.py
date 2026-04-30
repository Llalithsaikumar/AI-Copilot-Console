import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.collection import Collection

from app.auth.dependencies import get_current_user
from app.auth.models import UserCreate, UserLogin, TokenResponse, UserInDB
from app.auth.utils import hash_password, verify_password, create_access_token
from app.auth.mongodb import get_database
from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["authentication"])


def _get_user_collection() -> Collection:
    settings = get_settings()
    db = get_database(settings.mongodb_database)
    return db["users"]


@router.post("/register", status_code=200)
async def register(user: UserCreate):
    collection = _get_user_collection()
    existing = collection.find_one({"email": user.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    password_hash = hash_password(user.password)
    user_doc = {
        "email": user.email,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = collection.insert_one(user_doc)
    return {"user_id": str(result.inserted_id), "email": user.email}


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    collection = _get_user_collection()
    user_doc = collection.find_one({"email": credentials.email})
    if not user_doc or not verify_password(credentials.password, user_doc["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": str(user_doc["_id"])})
    return TokenResponse(access_token=access_token)


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    collection = _get_user_collection()
    user_doc = collection.find_one({"_id": __import__("bson").ObjectId(user_id)})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {
        "user_id": str(user_doc["_id"]),
        "email": user_doc["email"],
        "created_at": user_doc["created_at"],
    }
