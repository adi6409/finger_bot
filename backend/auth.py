from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# --- Configuration ---
SECRET_KEY = "YOUR_VERY_SECRET_KEY_REPLACE_THIS"  # Replace with a strong, secret key (e.g., generated via `openssl rand -hex 32`)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# tokenUrl should match the path of your token endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Pydantic Models ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# --- Utility Functions ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Dependency function to get the user database (will be overridden in main.py)
# This allows testing auth functions independently if needed
async def get_user_db():
    # This default implementation should ideally not be used directly in production endpoints
    # It's here to make the dependency resolvable by default.
    # In main.py, we'll provide the actual fake_users_db.
    print("Warning: Using default empty user DB in get_user_db")
    return {}


async def get_current_user(token: str = Depends(oauth2_scheme), users_db: dict = Depends(get_user_db)): # Inject users_db
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    # In a real app, you'd fetch the user from the database here
    user = users_db.get(email) # Use .get() for safer access
    if user is None:
        raise credentials_exception
    return user # Return the user object (or just email/ID)

# Dependency to get the current active user (can add checks like is_active here)
async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    # Add checks here if needed, e.g., if user is active
    # if not current_user.get("is_active"):
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
