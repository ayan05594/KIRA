# 🤖 KiRA - KIIT AI Chat Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-brightgreen.svg)](https://www.mongodb.com/cloud/atlas)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> An intelligent AI-powered chatbot assistant designed specifically for KIIT University students. Get instant answers about campus, courses, faculty, admissions, and more!

![KiRA Dashboard](https://via.placeholder.com/800x400/0f172a/38ef7d?text=KiRA+Chat+Interface)

---

## ✨ **Features**

### 🎯 **Core Features**
- 💬 **Intelligent Chat** - AI-powered responses using Google Gemini 2.5 Flash
- 🎤 **Voice Input/Output** - Speak your questions and hear responses
- 📥 **Chat Export** - Download conversations as TXT/PDF or copy to clipboard
- 👍👎 **Feedback System** - Rate responses to improve accuracy
- 🔍 **Search History** - Find past conversations instantly
- ✏️ **Message Editing** - Edit or delete your messages
- 📂 **Chat Sessions** - Organize conversations into multiple sessions

### 👤 **User Management**
- 🔐 **Secure Authentication** - Email/password with bcrypt hashing
- 🔑 **Password Reset** - OTP-based password recovery
- 👤 **User Profiles** - Manage personal information
- 📊 **Activity Analytics** - Track your usage with beautiful charts
- ⚙️ **Settings & Preferences** - Customize your experience

### 👨‍💼 **Admin Dashboard**
- 📈 **Real-time Statistics** - Monitor users, questions, and sessions
- 📊 **Analytics Charts** - Visualize user growth and engagement
- 👥 **User Management** - View and manage all users
- 🏆 **Top Users** - See most active users
- 💬 **Feedback Monitoring** - Track user satisfaction
- 🛡️ **Role Management** - Promote users to admin

### 🎨 **UI/UX**
- 🌙 **Modern Dark Theme** - Beautiful gradient design
- 📱 **Fully Responsive** - Works on all devices
- ♿ **Accessible** - WCAG compliant
- 🎭 **Smooth Animations** - Polished user experience
- 🍞 **Toast Notifications** - Non-intrusive feedback

---

## 🚀 **Quick Start**

### **Prerequisites**

- Python 3.11+
- MongoDB Atlas account
- Google Gemini API key
- Gmail account (for email features)

### **Installation**

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/kira-chatbot.git
cd kira-chatbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp env.example .env
# Edit .env and add your credentials

# Run the application
python3 app.py
```

Visit `http://localhost:5001` in your browser.

---

## 🔧 **Configuration**

### **Environment Variables**

Create a `.env` file in the root directory:

```bash
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# MongoDB Configuration
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/kira

# Google Gemini API
GEMINI_API_KEY=your-gemini-api-key

# Email Configuration
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
ADMIN_EMAIL=admin@kiit.ac.in

# Application Settings
PORT=5001
```

### **Getting API Keys**

1. **MongoDB Atlas:**
   - Sign up at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
   - Create a free cluster
   - Get connection string

2. **Google Gemini API:**
   - Visit [ai.google.dev](https://ai.google.dev)
   - Create API key

3. **Gmail App Password:**
   - Enable 2FA on your Google account
   - Generate app password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

---

## 📚 **Usage**

### **For Students**

1. **Register** with your KIIT email (`@kiit.ac.in`)
2. **Ask questions** about campus, courses, faculty, etc.
3. **Use voice input** for hands-free interaction
4. **Export chats** to save important information
5. **Rate responses** to help improve the bot

### **For Admins**

1. **Get promoted** to admin:
   ```bash
   python3 make_admin.py your-email@kiit.ac.in
   ```

2. **Access dashboard** at `/admin`

3. **Monitor** user activity and feedback

4. **Manage** users and promote other admins

---

## 🏗️ **Project Structure**

```
kira-chatbot/
├── app.py                  # Main Flask application
├── data.txt               # Knowledge base
├── templates/             # HTML templates
│   ├── chat.html         # Main chat interface
│   ├── profile.html      # User profile
│   ├── admin.html        # Admin dashboard
│   ├── settings.html     # User settings
│   ├── loginpage.html    # Login page
│   ├── registrationpage.html
│   ├── about.html
│   ├── contact.html
│   └── error.html
├── static/               # Static assets
│   ├── images/
│   └── manifest.json
├── requirements.txt      # Python dependencies
├── Procfile             # Heroku deployment
├── render.yaml          # Render deployment
├── railway.json         # Railway deployment
├── gunicorn_config.py   # Production server config
├── make_admin.py        # Admin promotion script
├── deploy.sh            # Deployment helper script
├── DEPLOYMENT_GUIDE.md  # Deployment instructions
└── README.md            # This file
```

---

## 🌐 **Deployment**

### **Quick Deploy (Recommended)**

#### **Option 1: Render (Free)**

```bash
# Run deployment script
./deploy.sh

# Or manually:
# 1. Push to GitHub
# 2. Sign up on render.com
# 3. Connect repository
# 4. Deploy!
```

#### **Option 2: Railway**

```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
railway login
railway init
railway up
```

#### **Option 3: Heroku**

```bash
# Install Heroku CLI
brew install heroku

# Deploy
heroku login
heroku create kira-chatbot
git push heroku main
```

📖 **See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions**

---

## 🛠️ **Tech Stack**

### **Backend**
- **Flask** - Web framework
- **MongoDB** - Database
- **PyMongo** - MongoDB driver
- **Bcrypt** - Password hashing
- **Flask-Mail** - Email functionality
- **Flask-CORS** - Cross-origin support
- **Flask-Limiter** - Rate limiting
- **Gunicorn** - Production server

### **Frontend**
- **HTML5/CSS3** - Structure & styling
- **JavaScript (ES6+)** - Interactivity
- **Chart.js** - Analytics visualization
- **Font Awesome** - Icons
- **Web Speech API** - Voice features

### **AI & APIs**
- **Google Gemini 2.5 Flash** - AI responses
- **Gmail SMTP** - Email delivery

---

## 📊 **Features in Detail**

### **Chat Interface**
- Real-time AI responses
- Message history with timestamps
- Voice input and output
- Search functionality
- Export conversations
- Feedback buttons
- Message editing/deletion
- Multiple chat sessions

### **User Profile**
- Personal information management
- Activity timeline with charts
- Statistics dashboard
- Password change
- Settings management

### **Admin Dashboard**
- User statistics
- Growth analytics
- Top users ranking
- Feedback monitoring
- User management
- Role assignment

### **Security**
- Password hashing with bcrypt
- CSRF protection
- Rate limiting
- Email validation
- Session management
- Input sanitization

---

## 🤝 **Contributing**

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 **Author**

**KIIT University**
- Email: 22052627@kiit.ac.in
- GitHub: [@yourusername](https://github.com/yourusername)

---

## 🙏 **Acknowledgments**

- Google Gemini for AI capabilities
- KIIT University for inspiration
- All contributors and users

---

## 📞 **Support**

- 📧 Email: support@kiit.ac.in
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/kira-chatbot/issues)
- 📖 Documentation: [Wiki](https://github.com/yourusername/kira-chatbot/wiki)

---

## 🗺️ **Roadmap**

- [ ] Multi-language support
- [ ] Mobile app (React Native)
- [ ] Advanced analytics
- [ ] Integration with KIIT systems
- [ ] Voice commands
- [ ] File uploads
- [ ] Group chat support
- [ ] API for third-party integrations

---

## 📸 **Screenshots**

### Chat Interface
![Chat Interface](https://via.placeholder.com/800x500/0f172a/38ef7d?text=Chat+Interface)

### Admin Dashboard
![Admin Dashboard](https://via.placeholder.com/800x500/0f172a/38ef7d?text=Admin+Dashboard)

### User Profile
![User Profile](https://via.placeholder.com/800x500/0f172a/38ef7d?text=User+Profile)

---

## ⭐ **Star History**

If you find this project useful, please consider giving it a star!

---

<div align="center">

**Made with ❤️ for KIIT University Students**

[Report Bug](https://github.com/yourusername/kira-chatbot/issues) · [Request Feature](https://github.com/yourusername/kira-chatbot/issues) · [Documentation](https://github.com/yourusername/kira-chatbot/wiki)

</div>

