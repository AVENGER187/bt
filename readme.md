# 🎬 Filmo - Film Production Collaboration Platform

A comprehensive backend API for connecting filmmakers, crew members, and talent for collaborative film projects. Built with FastAPI and PostgreSQL.

## 🌟 Features

### Core Functionality
- **User Management** - Profile creation with skills, experience, and portfolio
- **Project Creation** - Create and manage film projects with multiple roles
- **Smart Search** - Find projects by skills, location, type, and distance
- **Application System** - Apply to roles and manage applications
- **Real-time Chat** - WebSocket-based project chat with online presence
- **Team Management** - Hierarchical role system (Admin, Parent, Child)

### Advanced Features
- **Location-based Search** - Find projects and users within specified distance (Haversine formula)
- **Skill Matching** - Match users to projects based on required skills
- **File Upload** - Profile photos and portfolio files via Supabase Storage
- **Automated Cleanup** - Scheduled tasks for stale projects and expired data
- **Email Verification** - OTP-based authentication with professional HTML email templates
- **Optimized Queries** - Eliminated N+1 queries throughout for production-grade performance

## 🛠️ Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (Supabase)
- **ORM**: SQLAlchemy 2.0 (async)
- **Authentication**: JWT + Argon2 password hashing
- **Storage**: Supabase Storage
- **Email**: SMTP (Gmail)
- **Scheduler**: APScheduler
- **WebSockets**: Native FastAPI WebSocket support

## 📁 Project Structure

```
.
├── routers/
│   ├── auth.py              # Authentication (signup, login, OTP, password reset)
│   ├── profile.py           # User profile management
│   ├── projects.py          # Project CRUD operations
│   ├── application.py       # Job applications & acceptance
│   ├── search.py            # Search projects & users with filters
│   ├── chat.py              # Real-time WebSocket chat
│   ├── management.py        # Project team management
│   ├── skills.py            # Skills CRUD
│   └── upload.py            # File uploads (images, videos, PDFs)
├── database/
│   ├── schemas.py           # SQLAlchemy models & relationships
│   └── initialization.py    # Database engine & session setup
├── utils/
│   ├── auth.py              # JWT & password utilities
│   ├── email.py             # Email sending with HTML templates
│   ├── cleanup.py           # Automated cleanup tasks
│   └── scheduler.py             # Background job scheduler
├── config.py                # Environment configuration
└── main.py                  # Application entry point
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database (Supabase recommended)
- Gmail account with App Password (for SMTP)
- Supabase account (for file storage)

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd filmo-backend
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database

# Email (Gmail)
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# JWT Authentication
SECRET_KEY=<generate-a-secure-random-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_HOURS=1
REFRESH_TOKEN_EXPIRE_DAYS=30

# Frontend
FRONTEND_LINK=http://localhost:3000

# Supabase Storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
```

**Generate a secure SECRET_KEY:**
```python
import secrets
print(secrets.token_urlsafe(32))
```

5. **Initialize the database**

Run the seed script to populate skills:
```bash
python seed_skills.py
```

6. **Run the application**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

## 📚 API Endpoints

### Authentication
- `POST /auth/signup/send-otp` - Send OTP for registration
- `POST /auth/signup/verify-otp/{email}` - Verify OTP and create account
- `POST /auth/login` - Login with email/password
- `POST /auth/refresh` - Refresh access token
- `POST /auth/reset-password/send-otp` - Send OTP for password reset
- `POST /auth/reset-password/{email}` - Reset password with OTP

### Profile
- `POST /profile/create` - Create user profile
- `GET /profile/me` - Get current user profile
- `PUT /profile/update` - Update profile

### Projects
- `POST /projects/create` - Create new project
- `GET /projects/{project_id}` - Get project details
- `GET /projects/my/projects` - Get user's created projects
- `GET /projects/my/memberships` - Get projects user is a member of
- `PUT /projects/{project_id}` - Update project

### Search
- `GET /search/projects` - Search projects (with filters: skill, type, location, distance)
- `GET /search/users` - Search users (with filters: name, profession, skill, location)

### Applications
- `POST /applications/apply` - Apply to a project role
- `GET /applications/project/{project_id}` - Get project applications
- `GET /applications/my-applications` - Get user's applications
- `POST /applications/accept/{application_id}` - Accept application
- `POST /applications/reject/{application_id}` - Reject application

### Team Management
- `PUT /management/project/{project_id}/status` - Update project status
- `PUT /management/project/{project_id}/member/{user_id}/promote` - Promote/demote member
- `GET /management/project/{project_id}/members` - Get project members
- `DELETE /management/project/{project_id}/member/{user_id}` - Remove member
- `POST /management/project/{project_id}/leave` - Leave project
- `GET /management/project/{project_id}/stats` - Get project statistics

### Chat
- `WS /chat/ws/{project_id}` - WebSocket connection for real-time chat
- `GET /chat/messages/{project_id}` - Get message history (paginated)
- `DELETE /chat/message/{message_id}` - Delete message
- `GET /chat/online-users/{project_id}` - Get online users

### Skills
- `POST /skills/create` - Create new skill
- `GET /skills/list` - List all skills (with optional category filter)
- `GET /skills/categories` - Get all skill categories
- `GET /skills/{skill_id}` - Get skill by ID

### File Upload
- `POST /upload/profile-photo` - Upload profile photo (max 5MB)
- `POST /upload/portfolio` - Upload portfolio file (max 50MB)
- `DELETE /upload/profile-photo` - Delete profile photo

## 🗄️ Database Schema

### Core Models
- **Users** - Authentication and account info
- **UserProfiles** - Profile data, skills, location, portfolio
- **Projects** - Film projects with roles and requirements
- **ProjectRoles** - Specific roles within projects
- **Applications** - Job applications to project roles
- **ProjectMembers** - Team members with hierarchical roles
- **Messages** - Real-time chat messages
- **Skills** - Categorized skills database

### Enums
- **ProjectType**: short_film, feature_film, series, documentary, music_video, commercial, other
- **ProjectStatus**: active, completed, shelved, disposed, dead
- **PaymentType**: paid, unpaid, negotiable
- **ApplicationStatus**: pending, accepted, rejected
- **MemberRole**: admin, parent, child
- **Gender**: male, female, other, prefer_not_to_say

## 🔒 Security Features

- **Argon2 Password Hashing** - Industry-standard password security
- **JWT Authentication** - Stateless auth with access & refresh tokens
- **OTP Email Verification** - 6-digit codes with 5-minute expiry
- **Token Rotation** - Refresh tokens are revoked after use
- **CORS Protection** - Configurable allowed origins
- **Rate Limiting Ready** - Structure supports future rate limiting
- **Input Validation** - Pydantic models validate all inputs
- **SQL Injection Protection** - SQLAlchemy parameterized queries

## 🔄 Automated Tasks

The scheduler runs daily at 2:00 AM UTC to perform cleanup:

1. **Stale Projects** - Mark projects inactive for 30+ days as DEAD
2. **Expired OTPs** - Delete OTP codes older than 1 day
3. **Revoked Tokens** - Delete revoked refresh tokens older than 30 days

## 🎯 Key Features Explained

### Location-Based Search
Uses the Haversine formula to calculate distances between coordinates:
```python
# Example: Find projects within 50km
GET /search/projects?latitude=40.7128&longitude=-74.0060&max_distance_km=50
```

### Real-time Chat
WebSocket implementation with:
- Online user presence tracking
- User join/leave notifications
- Ping/pong heartbeat
- Message history with pagination

### Application Workflow
1. User applies to a role
2. Project admin/parent reviews applications
3. On acceptance:
   - User becomes project member
   - Role slot fills up
   - Application status updates
   - Project marked as fully staffed when all roles filled

### Role Hierarchy
- **Admin** - Full control (creator by default)
- **Parent** - Can manage team and update status
- **Child** - Regular team member

## 📊 Performance Optimizations

- **Eliminated N+1 Queries** - All list endpoints use JOINs
- **Bulk Operations** - Skill assignments use bulk inserts
- **Pagination** - All search and list endpoints paginated
- **Database Indexes** - Strategic indexes on frequently queried columns
- **Connection Pooling** - Configured for Supabase limits
- **Async Throughout** - Fully async/await implementation

## 🧪 Example Requests

### Create Profile
```json
POST /profile/create
{
  "name": "John Doe",
  "age": 28,
  "gender": "male",
  "profession": "Director of Photography",
  "bio": "Experienced DP with 5 years in indie films",
  "is_actor": false,
  "city": "Los Angeles",
  "state": "California",
  "country": "United States",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "years_of_experience": 5,
  "skill_ids": [5, 6, 8]
}
```

### Create Project
```json
POST /projects/create
{
  "name": "Indie Short Film - The Last Light",
  "description": "A 15-minute sci-fi short about humanity's final moments",
  "project_type": "short_film",
  "city": "Los Angeles",
  "state": "California",
  "country": "United States",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "roles": [
    {
      "skill_id": 5,
      "role_title": "Director of Photography",
      "description": "Experienced DP needed",
      "slots_available": 1,
      "payment_type": "paid",
      "payment_amount": 500.0
    }
  ]
}
```

### Search Projects
```json
GET /search/projects?skill_id=5&latitude=34.0522&longitude=-118.2437&max_distance_km=50&page=1&limit=20
```

## 🐛 Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URL` format: `postgresql+asyncpg://...`
- Check Supabase connection limit (60 on free tier)
- Ensure SSL is required: `ssl=require`

### Email Not Sending
- Use Gmail App Password, not regular password
- Enable "Less secure app access" if needed
- Check SMTP credentials in `.env`

### WebSocket Connection Fails
- Send authentication token in first message
- Ensure user is a project member
- Check CORS settings for WebSocket origin

## 📝 Environment Setup

### Gmail App Password
1. Enable 2FA on Google account
2. Go to Google Account > Security > App Passwords
3. Generate password for "Mail"
4. Use this in `SMTP_PASSWORD`

### Supabase Setup
1. Create Supabase project
2. Get database URL from Settings > Database
3. Create storage buckets: `profile-photos`, `portfolio-files`
4. Set bucket policies to public read

## 🚀 Deployment

### Production Checklist
- [ ] Set `echo=False` in database engine
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure CORS for production frontend URL
- [ ] Set up database backups
- [ ] Enable logging to file/service
- [ ] Set up monitoring (e.g., Sentry)
- [ ] Configure rate limiting
- [ ] Use environment-specific configs
- [ ] Set up CI/CD pipeline
- [ ] Enable HTTPS only

### Recommended Services
- **Hosting**: Railway, Render, Fly.io
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Monitoring**: Sentry, LogRocket
- **Email**: Gmail SMTP or SendGrid

## 📄 License

[Your License Here]

## 👥 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📧 Contact

[Your Contact Info]

---

Built with ❤️ for the filmmaking community