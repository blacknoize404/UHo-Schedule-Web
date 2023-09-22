import datetime
import json
import os
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import fastapi
import hashlib

app = FastAPI()
server_private_storage_address = "storage/private"
server_public_storage_address = "storage/public"
server_name = "test0"
server_version = 1

administrator_users = [
    "root",
    "Barnés"
]

delete_salt = "delete"


@app.get("/")
async def root():
    return RedirectResponse("/manifest")


@app.get("/manifest")
async def get_manifest():

    return JSONResponse(generate_manifest())


@app.get("/privileged_users")
async def get_privileged_users():

    response = {
        "priviledged_users": []
    }

    priviledged_users = []

    for value in administrator_users:
        priviledged_users.append(generate_sha1_from_string(value))

    response.update({"priviledged_users": priviledged_users})

    return JSONResponse(response)


@app.post("/validate_user")
async def validate_user(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")

    user = data["username"]
    user_hash = generate_sha1_from_string(user)
    if (not check_if_user_is_priviledged(user_hash)):
        raise HTTPException(status_code=401, detail="Unauthorized")

    return fastapi.responses.HTMLResponse("Success")


@app.post("/upload_user_schedule")
async def upload_user_schedule(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")

    file_hash = generate_user_schedule_sha1(data)
    file_address = f"private/{file_hash}"

    try:
        # Create the necessary directories if they don't exist
        create_folders(f"storage/{file_address}.json")

        with open(f"storage/{file_address}.json", 'w', encoding="UTF-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Retorno la url generada
        return {"file_hash": file_hash}

    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save schedule")


@app.head("/get_private")
@app.get("/get_private")
async def get_user_schedule(hash : str):
    if (not hash):
        raise HTTPException(status_code=400, detail="Bad Request")

    try:
        f = open(
            f"{server_private_storage_address}/{hash}.json", encoding="UTF-8")
        
        data = json.load(f)
        
        data["lastTimeDownloaded"] = get_actual_day_formatted()
        
        with open(f"{server_private_storage_address}/{hash}.json", 'w', encoding="UTF-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return JSONResponse(data)
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")


@app.post("/remove_user_schedule")
async def remove_user_schedule(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")

    file_hash = data["file_hash"]
    recieved_hash = data["salted_hash"]

    if (not generate_sha1_from_string(delete_salt+file_hash) == recieved_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")

    file_address = f"storage/private/{file_hash}.json"

    if (not check_if_file_exist(f"{file_address}")):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        os.remove(f"{file_address}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to delete schedule")

    return fastapi.responses.HTMLResponse("Success")


@app.post("/upload_school_schedule")
async def upload_school_schedule(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")

    # Comprobando que el autor tenga permisos para guardar el horario
    author = generate_sha1_from_string(data["author"])
    if (not check_if_user_is_priviledged(author)):
        raise HTTPException(status_code=403, detail="Not allowed")

    file_hash = generate_school_schedule_sha1(data)

    academy = data["academy"]
    faculty = data["faculty"]

    file_address = f"public/{academy}/{faculty}/{file_hash}"

    try:
        # Create the necessary directories if they don't exist
        create_folders(f"storage/{file_address}.json")

        with open(f"storage/{file_address}.json", 'w', encoding="UTF-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Retorno la url generada
        return {"file_hash": file_hash}

    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save schedule")


@app.post("/get_public")
async def get_school_schedule(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")
    
    academy = data["academy"]
    faculty = data["faculty"]
    file_hash = data["file_hash"]
    
    try:
        f = open(
            f"{server_public_storage_address}/{academy}/{faculty}/{file_hash}.json", encoding="UTF-8")
        data = json.load(f)
        
        data["lastTimeDownloaded"] = get_actual_day_formatted()
        
        with open(f"{server_public_storage_address}/{academy}/{faculty}/{file_hash}.json", 'w', encoding="UTF-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return JSONResponse(data)
    except Exception:
        raise HTTPException(status_code=404, detail="Schedule not found")


@app.post("/remove_school_schedule")
async def remove_school_schedule(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Bad Request")

    if (not data):
        raise HTTPException(status_code=400, detail="Bad Request")

    academy = data["academy"]
    faculty = data["faculty"]
    file_hash = data["file_hash"]
    recieved_hash = data["salted_hash"]

    # Generación de un propio hash para comparar con el enviado
    if (not generate_sha1_from_string(delete_salt+file_hash) == recieved_hash):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Comprobación de que existe el archivo
    file_address = f"storage/public/{academy}/{faculty}/{file_hash}.json"

    if (not check_if_file_exist(f"{file_address}")):
        raise HTTPException(status_code=404, detail="Not found")

    # Eliminación del archivo
    try:
        os.remove(f"{file_address}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to delete schedule")

    return fastapi.responses.HTMLResponse("Success")


def generate_manifest():
    response = {
        "serverName": server_name,
        "serverVersion": server_version,
        "academies": []
    }

    academies = []

    for academy in os.scandir(server_public_storage_address):
        if not academy.is_dir():
            continue

        academy_folder = academy.name

        print(academy_folder)

        academy = {
            "name": academy_folder,
            "faculties": []
        }

        faculties = []

        for academy_faculty in os.scandir(server_public_storage_address + '/' + academy_folder):

            if not academy_faculty.is_dir():
                continue

            faculty_folder = academy_faculty.name

            print(faculty_folder)

            faculty = {
                "name": faculty_folder,
                "schedules": []
            }

            schedules = []

            for faculty_schedule in os.scandir(server_public_storage_address + '/' + academy_folder + '/' + faculty_folder):

                if not faculty_schedule.is_file():
                    continue
                if not faculty_schedule.name.endswith(".json"):
                    continue

                schedule_file_name = faculty_schedule.name
                
                file_address = f"{server_public_storage_address}/{academy_folder}/{faculty_folder}/{schedule_file_name}"
                json_data = json.load(open(file_address, encoding="UTF-8"))

                schedule = {
                    "author": json_data["author"],
                    "formatVersion": json_data["formatVersion"],
                    "career": json_data["career"],
                    "year": json_data["year"],
                    "course": json_data["course"],
                    "courseType": json_data["courseType"],
                    "period": json_data["period"],
                    "createdDate": json_data["createdDate"],
                    "updatedDate": json_data["updatedDate"],
                    "lastTimeDownloaded": json_data["lastTimeDownloaded"],
                    "endDate": json_data["endDate"],
                    "hash": f"{schedule_file_name.removesuffix('.json')}"
                }

                schedules.append(schedule)

            faculty.update({"schedules": schedules})

            faculties.append(faculty)

        academy.update({"faculties": faculties})

        academies.append(academy)

    response.update({"academies": academies})

    return response


def generate_user_schedule_sha1(data: dict):

    createdDate = data["createdDate"]
    formatVersion = str(data["formatVersion"])
    scheduleName = data["scheduleName"]
    author = data["author"]

    return generate_sha1_from_string(
        createdDate+formatVersion+scheduleName+author
    )


def generate_school_schedule_sha1(data: dict):
    createdDate = data["createdDate"]
    formatVersion = str(data["formatVersion"])
    academy = data["academy"]
    faculty = data["faculty"]
    author = data["author"]
    career = data["career"]
    course = str(data["course"])
    courseType = data["courseType"]
    year = str(data["year"])
    period = str(data["period"])

    return generate_sha1_from_string(
        createdDate+formatVersion+academy +
        faculty+author+career+course +
        courseType+year+period
    )


def generate_sha1_from_string(data: str):

    # Convert the string to bytes
    my_bytes = data.encode('utf-8')

    # Generate the SHA-1 hash
    sha1_hash = hashlib.sha1(my_bytes).hexdigest()

    return sha1_hash


def check_if_file_exist(file_location: str):
    return os.path.exists(file_location)


def check_if_user_is_priviledged(username_hash: str):

    for value in administrator_users:
        if username_hash == generate_sha1_from_string(value):
            return True

    return False


def create_folders(path: str):
    # Create the necessary directories if they don't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)

# 2023-09-10 21:27:16
def get_actual_day_formatted():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")