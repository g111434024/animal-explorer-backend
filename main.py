from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 初始化 Supabase 客戶端
supabase_url = os.getenv("SUPABASE_URL", "https://rlkubwdazhrldybsuwcl.supabase.co")
supabase_key = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJsa3Vid2RhemhybGR5YnN1d2NsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk1OTg1MTEsImV4cCI6MjA3NTE3NDUxMX0.TcNP5Scu0fkE1ns1RwCd3DW1dDn-SxrbAvOfXS7XHtg")

# 檢查環境變數
print(f"Supabase URL: {supabase_url}")
print(f"Supabase Key: {supabase_key[:20]}...")

try:
    supabase: Client = create_client(supabase_url, supabase_key)
    print("Supabase client created successfully")
except Exception as e:
    print(f"Error creating Supabase client: {e}")
    raise

app = FastAPI(
    title="Animal Explorer API",
    description="動物探索系統的 API 服務",
    version="1.0.0"
)

# 允許跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 資料模型
class Animal(BaseModel):
    id: str
    name: str
    image: str
    summary: str
    description: str

class Comment(BaseModel):
    id: str
    text: str
    time: str
    user_name: Optional[str] = "匿名使用者"

class LikeData(BaseModel):
    count: int
    is_liked: bool

# 資料庫操作函數
async def get_animals_from_db():
    """從資料庫獲取所有動物"""
    try:
        response = supabase.table("animals").select("*").execute()
        return response.data
    except Exception as e:
        print(f"獲取動物資料錯誤: {e}")
        return []

async def get_animal_from_db(animal_id: str):
    """從資料庫獲取特定動物"""
    try:
        response = supabase.table("animals").select("*").eq("id", animal_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"獲取動物資料錯誤: {e}")
        return None

async def get_likes_from_db(animal_id: str, user_id: str = "default_user"):
    """從資料庫獲取按讚資料"""
    try:
        # 獲取總按讚數
        count_response = supabase.table("likes").select("id", count="exact").eq("animal_id", animal_id).eq("is_liked", True).execute()
        total_likes = count_response.count or 0
        
        # 檢查當前使用者是否已按讚
        user_like_response = supabase.table("likes").select("is_liked").eq("animal_id", animal_id).eq("user_id", user_id).execute()
        is_liked = user_like_response.data[0]["is_liked"] if user_like_response.data else False
        
        return {"count": total_likes, "is_liked": is_liked}
    except Exception as e:
        print(f"獲取按讚資料錯誤: {e}")
        return {"count": 0, "is_liked": False}

async def update_like_in_db(animal_id: str, is_liked: bool, user_id: str = "default_user"):
    """更新資料庫中的按讚狀態"""
    try:
        # 使用 upsert 來插入或更新按讚記錄
        response = supabase.table("likes").upsert({
            "animal_id": animal_id,
            "user_id": user_id,
            "is_liked": is_liked
        }).execute()
        return True
    except Exception as e:
        print(f"更新按讚資料錯誤: {e}")
        return False

async def get_comments_from_db(animal_id: str):
    """從資料庫獲取評論"""
    try:
        response = supabase.table("comments").select("*").eq("animal_id", animal_id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"獲取評論資料錯誤: {e}")
        return []

async def add_comment_to_db(animal_id: str, text: str, user_name: str = "匿名使用者"):
    """新增評論到資料庫"""
    try:
        response = supabase.table("comments").insert({
            "animal_id": animal_id,
            "text": text,
            "user_name": user_name
        }).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        print(f"新增評論錯誤: {e}")
        return None

# API 路由
@app.get("/")
async def root():
    return {"message": "Animal Explorer API", "version": "1.0.0"}

@app.get("/animals", response_model=List[Animal])
async def get_animals():
    """取得所有動物清單"""
    animals = await get_animals_from_db()
    return animals

@app.get("/animals/{animal_id}", response_model=Animal)
async def get_animal(animal_id: str):
    """取得特定動物詳細資料"""
    animal = await get_animal_from_db(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="動物不存在")
    return animal

@app.get("/animals/{animal_id}/likes", response_model=LikeData)
async def get_likes(animal_id: str):
    """取得動物的按讚資料"""
    # 檢查動物是否存在
    animal = await get_animal_from_db(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="動物不存在")
    
    like_data = await get_likes_from_db(animal_id)
    return LikeData(**like_data)

@app.post("/animals/{animal_id}/likes", response_model=LikeData)
async def toggle_like(animal_id: str, like_data: LikeData):
    """切換動物的按讚狀態"""
    # 檢查動物是否存在
    animal = await get_animal_from_db(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="動物不存在")
    
    # 更新資料庫中的按讚狀態
    success = await update_like_in_db(animal_id, like_data.is_liked)
    if not success:
        raise HTTPException(status_code=500, detail="更新按讚狀態失敗")
    
    # 返回更新後的按讚資料
    updated_like_data = await get_likes_from_db(animal_id)
    return LikeData(**updated_like_data)

@app.get("/animals/{animal_id}/comments", response_model=List[Comment])
async def get_comments(animal_id: str):
    """取得動物的評論清單"""
    # 檢查動物是否存在
    animal = await get_animal_from_db(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="動物不存在")
    
    comments = await get_comments_from_db(animal_id)
    return comments

@app.post("/animals/{animal_id}/comments", response_model=Comment)
async def add_comment(animal_id: str, comment: Comment):
    """新增動物評論"""
    # 檢查動物是否存在
    animal = await get_animal_from_db(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail="動物不存在")
    
    # 新增評論到資料庫
    new_comment = await add_comment_to_db(animal_id, comment.text, comment.user_name if hasattr(comment, 'user_name') else "匿名使用者")
    if not new_comment:
        raise HTTPException(status_code=500, detail="新增評論失敗")
    
    return Comment(
        id=str(new_comment["id"]),
        text=new_comment["text"],
        time=new_comment["created_at"]
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)