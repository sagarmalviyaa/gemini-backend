# Gemini Backend Clone

A comprehensive backend system that enables user-specific chatrooms, OTP-based authentication, Google Gemini AI-powered conversations, and subscription handling via Stripe.

## Features

- **🔐 OTP-based Authentication**: Mobile number verification with JWT tokens
- **💬 AI Chatrooms**: Multiple chatrooms with Google Gemini API integration
- **⚡ Async Processing**: Message queue system using Celery and Redis
- **💳 Subscription Management**: Stripe integration with Basic/Pro tiers
- **🚀 Performance**: Redis caching and rate limiting
- **📊 Monitoring**: Health checks and comprehensive logging

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache/Queue**: Redis for caching and Celery for async tasks
- **AI Integration**: Google Gemini API
- **Payments**: Stripe (sandbox mode)
- **Deployment**: Docker containers

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   PostgreSQL    │    │      Redis      │
│                 │────│    Database     │    │  Cache/Queue    │
│  - API Routes   │    │                 │    │                 │
│  - Auth & JWT   │    │  - Users        │    │  - Sessions     │
│  - Rate Limiting│    │  - Chatrooms    │    │  - Rate Limits  │
│  - Validation   │    │  - Messages     │    │  - OTP Codes    │
└─────────────────┘    │  - Subscriptions│    └─────────────────┘
         │             └─────────────────┘             │
         │                                             │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Celery Worker  │    │   Gemini API    │    │   Stripe API    │
│                 │────│                 │    │                 │
│  - AI Processing│    │  - Chat         │    │  - Subscriptions│
│  - Async Tasks  │    │  - Responses    │    │  - Webhooks     │
│  - Queue Mgmt   │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## API Endpoints

### Authentication
- `POST /auth/signup` - Register user with mobile number
- `POST /auth/send-otp` - Send OTP to mobile (mocked)
- `POST /auth/verify-otp` - Verify OTP and get JWT token
- `POST /auth/forgot-password` - Send OTP for password reset
- `POST /auth/change-password` - Change user password

### User Management
- `GET /user/me` - Get current user information

### Chatroom Management
- `POST /chatroom` - Create new chatroom
- `GET /chatroom` - List user's chatrooms (cached)
- `GET /chatroom/{id}` - Get specific chatroom details
- `POST /chatroom/{id}/message` - Send message and get AI response

### Subscription Management
- `POST /subscribe/pro` - Initiate Pro subscription
- `GET /subscription/status` - Check subscription status
- `POST /webhook/stripe` - Handle Stripe webhook events

## Installation & Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### Local Development

1. **Clone and setup environment**:
```bash
git clone <repository-url>
cd gemini-backend
cp .env.example .env
```

2. **Configure environment variables** in `.env`:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/gemini_backend
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=your-super-secret-jwt-key-here
GEMINI_API_KEY=your-gemini-api-key-here
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_PRO_PRICE_ID=price_your_pro_price_id
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Start services**:
```bash
# Terminal 1: Start FastAPI app
uvicorn app.main:app --reload

# Terminal 2: Start Celery worker
celery -A app.celery_app worker --loglevel=info -Q ai_processing --pool=solo

# Terminal 3: Start Celery Flower (optional monitoring)
celery -A app.celery_app flower
```

### Docker Development

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `REDIS_URL` | Redis connection string | Yes |
| `JWT_SECRET_KEY` | JWT signing secret | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `STRIPE_SECRET_KEY` | Stripe secret key | Yes |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret | Yes |
| `STRIPE_PRO_PRICE_ID` | Stripe Pro plan price ID | Yes |

### Subscription Tiers

- **Basic (Free)**: 5 messages per day, basic features
- **Pro (Paid)**: Unlimited messages, priority support

### Rate Limiting

- Basic users: 5 messages per day (resets at UTC midnight)
- Pro users: 100 requests per minute
- Global: 1000 requests per minute per IP

## Caching Strategy

### Chatroom Caching
- **Endpoint**: `GET /chatroom`
- **TTL**: 5 minutes (300 seconds)
- **Key Pattern**: `chatrooms:user:{user_id}`
- **Justification**: Frequently accessed when loading dashboard; chatrooms don't change often

### Rate Limiting Cache
- **Purpose**: Track daily message counts for Basic users
- **TTL**: 24 hours (auto-expires at midnight)
- **Key Pattern**: `rate_limit:user:{user_id}:date:{date}`

### OTP Cache
- **Purpose**: Store OTP codes with automatic expiration
- **TTL**: 5 minutes
- **Key Pattern**: `otp:{mobile_number}`

## Message Queue System

### Celery Configuration
- **Broker**: Redis
- **Serialization**: JSON
- **Task Time Limit**: 30 minutes
- **Retry Strategy**: Exponential backoff (max 3 retries)

### Queue Tasks
- `process_gemini_message`: Process AI conversations asynchronously
- Queue: `ai_processing` (high priority)
- Monitoring: Flower dashboard at http://localhost:5555

## Testing

### API Testing with Postman

1. **Import Collection**: Use the provided Postman collection
2. **Set Environment Variables**:
   - `base_url`: http://localhost:8000
   - `auth_token`: JWT token from login

3. **Test Flow**:
   ```
   1. POST /auth/signup (register user)
   2. POST /auth/send-otp (get OTP)
   3. POST /auth/verify-otp (login with OTP)
   4. GET /user/me (verify authentication)
   5. POST /chatroom (create chatroom)
   6. GET /chatroom (list chatrooms)
   7. POST /chatroom/{id}/message (send message)
   8. GET /subscription/status (check subscription)
   ```

### Health Checks

- `GET /health` - Application health status
- `GET /` - Root endpoint with API information

## Deployment

### Cloud Platforms
Recommended platforms: Railway, Render, Fly.io, AWS ECS

### Environment Setup
1. Set all required environment variables
2. Configure PostgreSQL and Redis services
3. Set up Stripe webhooks endpoint
4. Deploy with auto-scaling enabled

### Monitoring
- Application logs via structured logging
- Celery task monitoring via Flower
- Database connection pooling
- Redis performance metrics

## Error Handling

### HTTP Status Codes
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (invalid/missing token)
- `403`: Forbidden (insufficient permissions)
- `404`: Not Found (resource doesn't exist)
- `429`: Too Many Requests (rate limited)
- `500`: Internal Server Error

### Error Response Format
```json
{
  "detail": "Error description",
  "status_code": 400,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Security Considerations

- JWT tokens with 24-hour expiration
- Input validation and sanitization
- SQL injection prevention via ORM
- Rate limiting protection
- CORS configuration
- Webhook signature verification
- Environment-based secrets management

## Development Guidelines

### Code Structure
```
app/
├── routers/          # API route handlers
├── models.py         # Database models
├── schemas.py        # Pydantic schemas
├── security.py       # Authentication logic
├── database.py       # Database connection
├── redis_client.py   # Redis operations
├── rate_limiter.py   # Rate limiting logic
├── celery_app.py     # Celery configuration
├── tasks.py          # Async tasks
├── gemini_client.py  # AI API client
├── stripe_client.py  # Payment API client
└── main.py           # FastAPI application
```

### Best Practices
- Use type hints throughout
- Implement proper error handling
- Add comprehensive logging
- Write unit tests for critical functions
- Follow RESTful API conventions
- Use dependency injection for database sessions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with proper tests
4. Submit a pull request with detailed description

## License

This project is created for educational and assessment purposes.

## Support

For issues and questions:
1. Check the logs for error details
2. Verify environment configuration
3. Test API endpoints with Postman
4. Review database and Redis connectivity

---

<!-- **Created for Kuvaka Tech Backend Developer Assessment** -->