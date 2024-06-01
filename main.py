import os
import uvicorn

PORT = os.environ.get("PORT", 8888)

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(PORT),
        reload=False,
        server_header=False,
        date_header=False,
    )
