# Troubleshooting Guide

## Issue: "Gagal memuat berita. Pastikan backend berjalan."

### Root Cause
Multiple Next.js development server instances were running simultaneously on different ports (3000, 3002, 3003), causing conflicts and connection issues.

### Solution Applied
1. Killed all running Next.js instances
2. Restarted frontend cleanly on port 3000
3. Verified backend is running on port 8000

### How to Fix in Future

#### Check Running Processes
```powershell
# Check if Next.js is running on multiple ports
netstat -ano | findstr :3000
netstat -ano | findstr :3002
netstat -ano | findstr :3003
```

#### Kill All Next.js Instances
```powershell
# Find all node processes running Next.js
Get-Process node | Where-Object { $_.Path -like "*node.exe*" }

# Kill by PID (replace with actual PID)
taskkill /PID <PID> /F

# Or kill all node processes (careful!)
taskkill /IM node.exe /F
```

#### Clean Restart
```bash
# In frontend directory
npm run dev
```

Expected output:
```
▲ Next.js 16.2.6 (Turbopack)
- Local:         http://localhost:3000
- Network:       http://192.168.18.88:3000
- Environments: .env.local
✓ Ready in 344ms
```

### Verify Services

#### Backend Health Check
```powershell
curl http://localhost:8000/health -UseBasicParsing
```

Expected response:
```json
{"status":"healthy"}
```

#### Backend News Endpoint
```powershell
curl "http://localhost:8000/news?category=terkini&limit=5" -UseBasicParsing
```

Should return JSON with articles array.

#### Frontend Page
Open browser: `http://localhost:3000/news`

### Configuration Check

#### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### Backend (.env)
```env
FRONTEND_URL=http://localhost:3000
LLM_API_KEY=sk-or-v1-...
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-5-mini
LLM_WEB_SEARCH=true
LLM_WEB_ENGINE=exa
```

### CORS Issues

If you see CORS errors in browser console:

1. Check backend CORS configuration in `backend/app/main.py`
2. Verify `FRONTEND_URL` in backend `.env` includes your frontend URL
3. Restart backend after changing CORS settings

### Test HTML Tool

Use `test_frontend_connection.html` for quick testing:
```bash
# Open in browser
start test_frontend_connection.html
```

Click buttons to test:
- `/health` endpoint
- `/news` endpoint

## Current Status

✅ **Backend**: Running on http://localhost:8000
✅ **Frontend**: Running on http://localhost:3000
✅ **Connection**: Verified working
✅ **CORS**: Configured correctly

## Common Issues

### Port Already in Use
```
⚠ Port 3000 is in use by process 5972
```

**Solution**: Kill the process using that port:
```powershell
# Find process
netstat -ano | findstr :3000

# Kill process (use PID from above)
taskkill /PID <PID> /F
```

### Backend Not Responding
```
Tidak dapat terhubung ke server
```

**Check**:
1. Is backend running? `curl http://localhost:8000/health`
2. Check backend logs for errors
3. Verify `.env` configuration
4. Check if uvicorn process is running: `Get-Process | Where-Object { $_.ProcessName -like "*python*" }`

### Timeout Errors
```
Ringkasan memakan waktu terlalu lama (timeout)
```

**Causes**:
- LLM API slow response (OpenRouter/Firecrawl)
- Rate limits
- Network issues

**Solutions**:
- Wait and retry
- Check API key quota
- Use faster model (gpt-5-mini instead of free models)
