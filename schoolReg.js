import React, { useState, useEffect } from 'react';
import { School, Eye, EyeOff, LogIn, Shield, Users, BookOpen, BarChart3, Settings, Calendar, FileText, GraduationCap, UserCheck, ClipboardList, ArrowLeft, Mail } from 'lucide-react';

const SchoolLoginDashboard = () => {
  const [loginData, setLoginData] = useState({
    schoolId: '',
    password: '',
    rememberMe: false
  });
  
  const [showPassword, setShowPassword] = useState(false);
  const [loginStep, setLoginStep] = useState('form'); // 'form', 'authenticating', 'dashboard', 'forgotPassword'
  const [forgotPasswordData, setForgotPasswordData] = useState({
    schoolId: '',
    email: ''
  });
  const [errors, setErrors] = useState({});
  const [schoolInfo, setSchoolInfo] = useState({});
  const [successMessage, setSuccessMessage] = useState('');

  // Mock school data - in real app this comes from database
  const mockSchoolData = {
    'SCH_NYC_STMARY_001': {
      name: 'St. Mary\'s Elementary School',
      location: 'New York, NY',
      studentCount: 425,
      teacherCount: 28,
      principalName: 'Dr. Sarah Johnson',
      lastLogin: '2024-09-09 14:30:00'
    },
    'SCH_BOS_RIVER_002': {
      name: 'Riverside High School',
      location: 'Boston, MA', 
      studentCount: 850,
      teacherCount: 52,
      principalName: 'Mr. Michael Chen',
      lastLogin: '2024-09-08 09:15:00'
    }
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setLoginData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const handleForgotPasswordChange = (e) => {
    const { name, value } = e.target;
    setForgotPasswordData(prev => ({ ...prev, [name]: value }));
    
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validateLogin = () => {
    const newErrors = {};
    
    if (!loginData.schoolId.trim()) {
      newErrors.schoolId = 'School ID is required';
    }
    
    if (!loginData.password.trim()) {
      newErrors.password = 'Password is required';
    } else if (loginData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const goToForgotPassword = () => {
    setLoginStep('forgotPassword');
    setErrors({});
  };

  const backToLogin = () => {
    setLoginStep('form');
    setErrors({});
    setForgotPasswordData({ schoolId: '', email: '' });
  };

  const handleForgotPassword = async () => {
    const newErrors = {};
    
    if (!forgotPasswordData.schoolId.trim()) {
      newErrors.schoolId = 'School ID is required';
    }
    
    if (!forgotPasswordData.email.trim()) {
      newErrors.email = 'Email address is required';
    } else if (!/\S+@\S+\.\S+/.test(forgotPasswordData.email)) {
      newErrors.email = 'Please enter a valid email address';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    
    // Simulate password reset request
    setTimeout(() => {
      setSuccessMessage('Password reset instructions have been sent to your email address.');
      setTimeout(() => {
        setSuccessMessage('');
        setLoginStep('form');
        setForgotPasswordData({ schoolId: '', email: '' });
      }, 3000);
    }, 1000);
  };

  const handleLogin = async () => {
    if (!validateLogin()) return;

    setLoginStep('authenticating');

    // Check if "Remember Me" is checked and store credentials
    if (loginData.rememberMe) {
      localStorage.setItem('rememberedSchoolId', loginData.schoolId);
    } else {
      localStorage.removeItem('rememberedSchoolId');
    }

    // Simulate authentication
    setTimeout(() => {
      // Mock authentication check
      const schoolData = mockSchoolData[loginData.schoolId];
      if (schoolData && loginData.password === 'password123') {
        setSchoolInfo(schoolData);
        setLoginStep('dashboard');
        
        // Store session if remember me is checked
        if (loginData.rememberMe) {
          localStorage.setItem('schoolSession', JSON.stringify({
            schoolId: loginData.schoolId,
            schoolInfo: schoolData,
            timestamp: new Date().getTime()
          }));
        }
      } else {
        setErrors({ 
          schoolId: 'Invalid School ID or Password',
          password: 'Invalid School ID or Password'
        });
        setLoginStep('form');
      }
    }, 1500);
  };

  const handleLogout = () => {
    setLoginStep('form');
    setLoginData({
      schoolId: localStorage.getItem('rememberedSchoolId') || '',
      password: '',
      rememberMe: localStorage.getItem('rememberedSchoolId') ? true : false
    });
    setSchoolInfo({});
    setErrors({});
    localStorage.removeItem('schoolSession');
  };

  // Check for remembered session on component mount
  useEffect(() => {
    const rememberedSchoolId = localStorage.getItem('rememberedSchoolId');
    const savedSession = localStorage.getItem('schoolSession');
    
    if (rememberedSchoolId) {
      setLoginData(prev => ({
        ...prev,
        schoolId: rememberedSchoolId,
        rememberMe: true
      }));
    }
    
    // Check if there's a valid saved session (within 7 days)
    if (savedSession) {
      try {
        const session = JSON.parse(savedSession);
        const sevenDaysInMs = 7 * 24 * 60 * 60 * 1000;
        const now = new Date().getTime();
        
        if (now - session.timestamp < sevenDaysInMs) {
          setSchoolInfo(session.schoolInfo);
          setLoginData(prev => ({
            ...prev,
            schoolId: session.schoolId,
            rememberMe: true
          }));
          setLoginStep('dashboard');
        } else {
          localStorage.removeItem('schoolSession');
        }
      } catch (e) {
        localStorage.removeItem('schoolSession');
      }
    }
  }, []);

  // Quick stats data
  const quickStats = [
    {
      title: 'Total Students',
      value: schoolInfo.studentCount || 0,
      icon: Users,
      color: 'bg-blue-500',
      change: '+12 this month'
    },
    {
      title: 'Total Teachers',
      value: schoolInfo.teacherCount || 0,
      icon: GraduationCap,
      color: 'bg-green-500',
      change: '+2 this semester'
    },
    {
      title: 'Present Today',
      value: Math.floor((schoolInfo.studentCount || 0) * 0.92),
      icon: UserCheck,
      color: 'bg-purple-500',
      change: '92% attendance'
    },
    {
      title: 'Classes Today',
      value: 24,
      icon: BookOpen,
      color: 'bg-orange-500',
      change: '6 periods'
    }
  ];

  const menuItems = [
    { 
      title: 'Students Management', 
      icon: Users, 
      description: 'Add, edit, and manage student records',
      count: schoolInfo.studentCount || 0
    },
    { 
      title: 'Teacher Management', 
      icon: GraduationCap, 
      description: 'Manage teaching staff and assignments',
      count: schoolInfo.teacherCount || 0
    },
    { 
      title: 'Attendance Tracking', 
      icon: UserCheck, 
      description: 'Record and monitor daily attendance',
      count: '92%'
    },
    { 
      title: 'Academic Records', 
      icon: BookOpen, 
      description: 'Manage grades and academic performance',
      count: 'Active'
    },
    { 
      title: 'Timetable & Scheduling', 
      icon: Calendar, 
      description: 'Create and manage class schedules',
      count: '6 periods'
    },
    { 
      title: 'Reports & Analytics', 
      icon: BarChart3, 
      description: 'Generate detailed school reports',
      count: '15 reports'
    },
    { 
      title: 'Assignments & Tests', 
      icon: ClipboardList, 
      description: 'Manage homework and examinations',
      count: '8 active'
    },
    { 
      title: 'School Settings', 
      icon: Settings, 
      description: 'Configure school-specific settings',
      count: 'Configure'
    }
  ];

  // Forgot Password Form
  if (loginStep === 'forgotPassword') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-blue-50 to-purple-50 animate-gradient-x">
        <div className="bg-white/80 backdrop-blur-sm shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center gap-3">
                <div className="bg-gradient-to-r from-indigo-600 to-blue-600 p-2 rounded-lg shadow-lg">
                  <School className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                    School Management Portal
                  </h1>
                  <p className="text-sm text-gray-500">Secure login for educational institutions</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-center p-4 py-12 min-h-[calc(100vh-4rem)]">
          <div className="max-w-md w-full animate-fade-in">
            <div className="text-center mb-8">
              <div className="flex justify-center mb-6">
                <div className="bg-white p-6 rounded-full shadow-2xl animate-bounce-slow">
                  <Shield className="h-16 w-16 text-indigo-600" />
                </div>
              </div>
              <h2 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-2">
                Reset Your Password
              </h2>
              <p className="text-gray-600">Enter your School ID and email to receive reset instructions</p>
            </div>

            <div className="bg-white/90 backdrop-blur-sm rounded-3xl shadow-2xl border border-white/50 p-8">
              {successMessage ? (
                <div className="text-center animate-scale-in">
                  <div className="bg-green-100 border border-green-300 rounded-2xl p-6 mb-6">
                    <div className="flex justify-center mb-4">
                      <div className="bg-green-500 rounded-full p-3 animate-pulse">
                        <Mail className="h-8 w-8 text-white" />
                      </div>
                    </div>
                    <p className="text-green-800 font-medium">{successMessage}</p>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-3">
                      School ID
                    </label>
                    <input
                      type="text"
                      name="schoolId"
                      value={forgotPasswordData.schoolId}
                      onChange={handleForgotPasswordChange}
                      className={`w-full px-4 py-4 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all duration-300 ${errors.schoolId ? 'border-red-300 bg-red-50 focus:border-red-400 animate-shake' : 'border-gray-200 focus:border-indigo-300 hover:border-gray-300'}`}
                      placeholder="Enter your School ID"
                    />
                    {errors.schoolId && <p className="text-red-500 text-sm mt-2 animate-fade-in">{errors.schoolId}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-3">
                      Email Address
                    </label>
                    <input
                      type="email"
                      name="email"
                      value={forgotPasswordData.email}
                      onChange={handleForgotPasswordChange}
                      className={`w-full px-4 py-4 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all duration-300 ${errors.email ? 'border-red-300 bg-red-50 focus:border-red-400 animate-shake' : 'border-gray-200 focus:border-indigo-300 hover:border-gray-300'}`}
                      placeholder="Enter your registered email"
                    />
                    {errors.email && <p className="text-red-500 text-sm mt-2 animate-fade-in">{errors.email}</p>}
                  </div>

                  <div className="space-y-4 pt-4">
                    <button
                      onClick={handleForgotPassword}
                      className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-xl font-bold hover:from-indigo-700 hover:to-purple-700 transition-all duration-200 flex items-center justify-center gap-3 shadow-xl hover:shadow-2xl transform hover:-translate-y-1"
                    >
                      <Mail className="h-5 w-5" />
                      Send Reset Instructions
                    </button>

                    <button
                      onClick={backToLogin}
                      className="w-full bg-gray-100 text-gray-700 px-6 py-4 rounded-xl font-semibold hover:bg-gray-200 transition-all duration-200 flex items-center justify-center gap-2"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      Back to Login
                    </button>
                  </div>
                </div>
              )}

              <div className="mt-8 bg-blue-50/70 rounded-2xl p-6 border border-blue-200">
                <div className="flex items-start gap-3">
                  <Shield className="h-5 w-5 text-blue-600 mt-1 flex-shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-blue-800">Security Notice</p>
                    <p className="text-xs text-blue-600 mt-1">
                      Password reset instructions will be sent to your registered email address. 
                      For security, the link will expire in 24 hours.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loginStep === 'authenticating') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-blue-800 to-purple-900 flex items-center justify-center p-4">
        <div className="bg-white/95 backdrop-blur-sm rounded-3xl shadow-2xl p-8 sm:p-12 max-w-lg w-full text-center animate-scale-in">
          <div className="relative mb-8">
            <div className="absolute inset-0 animate-ping rounded-full bg-indigo-400 opacity-25 h-20 w-20 mx-auto"></div>
            <div className="absolute inset-0 animate-ping rounded-full bg-blue-400 opacity-20 h-24 w-24 mx-auto" style={{animationDelay: '0.5s'}}></div>
            <div className="relative animate-spin rounded-full h-20 w-20 border-4 border-indigo-200 border-t-indigo-600 mx-auto"></div>
          </div>
          
          <h2 className="text-2xl sm:text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-6">
            Authenticating
          </h2>
          
          <div className="space-y-4 text-gray-600 mb-8">
            <div className="flex items-center justify-center gap-3 animate-fade-in">
              <div className="animate-pulse w-2 h-2 bg-indigo-500 rounded-full"></div>
              <span className="text-sm sm:text-base">Validating school credentials...</span>
            </div>
            <div className="flex items-center justify-center gap-3 animate-fade-in" style={{animationDelay: '0.5s'}}>
              <div className="animate-pulse w-2 h-2 bg-blue-500 rounded-full" style={{animationDelay: '0.5s'}}></div>
              <span className="text-sm sm:text-base">Loading school environment...</span>
            </div>
            <div className="flex items-center justify-center gap-3 animate-fade-in" style={{animationDelay: '1s'}}>
              <div className="animate-pulse w-2 h-2 bg-purple-500 rounded-full" style={{animationDelay: '1s'}}></div>
              <span className="text-sm sm:text-base">Preparing dashboard data...</span>
            </div>
          </div>

          <div className="bg-indigo-50 rounded-xl p-4">
            <p className="text-sm text-indigo-700 font-medium">
              Please wait while we set up your secure school environment...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (loginStep === 'dashboard') {
    return (
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center gap-3">
                <School className="h-8 w-8 text-indigo-600" />
                <div>
                  <h1 className="text-lg font-semibold text-gray-900">{schoolInfo.name}</h1>
                  <p className="text-sm text-gray-500">{schoolInfo.location} • ID: {loginData.schoolId}</p>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{schoolInfo.principalName}</p>
                  <p className="text-xs text-gray-500">School Principal</p>
                </div>
                <button 
                  onClick={handleLogout}
                  className="bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Welcome Section */}
          <div className="mb-8">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Welcome back, {schoolInfo.principalName}!
                </h2>
                <p className="text-gray-600">Here's what's happening at your school today.</p>
              </div>
              <div className="text-right text-sm text-gray-500">
                <p>Last login: {schoolInfo.lastLogin}</p>
                <p>Current time: {new Date().toLocaleString()}</p>
              </div>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {quickStats.map((stat, index) => {
              const IconComponent = stat.icon;
              return (
                <div key={index} className="bg-white rounded-xl shadow-sm p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-4">
                    <div className={`${stat.color} rounded-lg p-3`}>
                      <IconComponent className="h-6 w-6 text-white" />
                    </div>
                    <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
                      {stat.change}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-600 mb-1">{stat.title}</p>
                    <p className="text-3xl font-bold text-gray-900">{stat.value.toLocaleString()}</p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Quick Actions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-2">Quick Student Add</h3>
              <p className="text-blue-100 mb-4">Add new students to your school</p>
              <button className="bg-white text-blue-600 px-4 py-2 rounded-lg hover:bg-blue-50 transition-colors">
                Add Student
              </button>
            </div>

            <div className="bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-2">Take Attendance</h3>
              <p className="text-green-100 mb-4">Record today's attendance</p>
              <button className="bg-white text-green-600 px-4 py-2 rounded-lg hover:bg-green-50 transition-colors">
                Take Attendance
              </button>
            </div>

            <div className="bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-xl p-6">
              <h3 className="text-lg font-semibold mb-2">Generate Report</h3>
              <p className="text-purple-100 mb-4">Create academic reports</p>
              <button className="bg-white text-purple-600 px-4 py-2 rounded-lg hover:bg-purple-50 transition-colors">
                Generate Report
              </button>
            </div>
          </div>

          {/* Main Menu */}
          <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
            <h3 className="text-xl font-semibold text-gray-900 mb-6">School Management</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {menuItems.map((item, index) => {
                const IconComponent = item.icon;
                return (
                  <div 
                    key={index}
                    className="border border-gray-200 rounded-lg p-6 hover:border-indigo-300 hover:shadow-md transition-all cursor-pointer group"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="bg-indigo-50 rounded-lg p-3 group-hover:bg-indigo-100 transition-colors">
                        <IconComponent className="h-6 w-6 text-indigo-600" />
                      </div>
                      <span className="text-sm font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded">
                        {item.count}
                      </span>
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900 mb-2">{item.title}</h4>
                      <p className="text-sm text-gray-600">{item.description}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-6">Recent Activity</h3>
            <div className="space-y-4">
              <div className="flex items-center gap-4 p-4 bg-blue-50 rounded-lg">
                <div className="bg-blue-500 rounded-full p-2">
                  <UserCheck className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">Daily attendance recorded</p>
                  <p className="text-sm text-gray-600">92% attendance rate for today • 389 students present</p>
                </div>
                <span className="text-sm text-gray-500">2 hours ago</span>
              </div>
              
              <div className="flex items-center gap-4 p-4 bg-green-50 rounded-lg">
                <div className="bg-green-500 rounded-full p-2">
                  <FileText className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">Monthly report generated</p>
                  <p className="text-sm text-gray-600">Academic performance summary ready for September</p>
                </div>
                <span className="text-sm text-gray-500">1 day ago</span>
              </div>
              
              <div className="flex items-center gap-4 p-4 bg-purple-50 rounded-lg">
                <div className="bg-purple-500 rounded-full p-2">
                  <Users className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">New student registrations</p>
                  <p className="text-sm text-gray-600">5 new students admitted this week</p>
                </div>
                <span className="text-sm text-gray-500">3 days ago</span>
              </div>

              <div className="flex items-center gap-4 p-4 bg-orange-50 rounded-lg">
                <div className="bg-orange-500 rounded-full p-2">
                  <Calendar className="h-5 w-5 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-gray-900">Timetable updated</p>
                  <p className="text-sm text-gray-600">New schedule for Grade 10 published</p>
                </div>
                <span className="text-sm text-gray-500">5 days ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-blue-50 to-purple-50 animate-gradient-x">
      {/* Enhanced Header */}
      <div className="bg-white/90 backdrop-blur-md shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16 sm:h-20">
            <div className="flex items-center gap-3">
              <div className="bg-gradient-to-r from-indigo-600 to-blue-600 p-2 sm:p-3 rounded-xl shadow-lg animate-pulse-slow">
                <School className="h-6 w-6 sm:h-7 sm:w-7 text-white" />
              </div>
              <div>
                <h1 className="text-lg sm:text-xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
                  School Management Portal
                </h1>
                <p className="text-xs sm:text-sm text-gray-500">Secure login for educational institutions</p>
              </div>
            </div>
            
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Shield className="h-4 w-4 text-green-500 animate-pulse" />
              <span className="hidden sm:inline">SSL Secured</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-center p-4 py-8 sm:py-12 min-h-[calc(100vh-5rem)]">
        <div className="max-w-md w-full animate-fade-in-up">
          {/* Enhanced Login Card Header */}
          <div className="text-center mb-8 sm:mb-12">
            <div className="flex justify-center mb-6">
              <div className="bg-white/80 backdrop-blur-sm p-6 sm:p-8 rounded-full shadow-2xl animate-float">
                <School className="h-12 w-12 sm:h-16 sm:w-16 text-indigo-600" />
              </div>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-3 animate-text-shimmer">
              Welcome Back
            </h2>
            <p className="text-gray-600 text-base sm:text-lg">Sign in to your school management dashboard</p>
          </div>

          {/* Enhanced Login Form */}
          <div className="bg-white/90 backdrop-blur-sm rounded-3xl shadow-2xl border border-white/50 p-6 sm:p-8 animate-scale-in">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  School ID
                </label>
                <input
                  type="text"
                  name="schoolId"
                  value={loginData.schoolId}
                  onChange={handleInputChange}
                  className={`w-full px-4 py-4 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all duration-300 ${errors.schoolId ? 'border-red-300 bg-red-50 focus:border-red-400 animate-shake' : 'border-gray-200 focus:border-indigo-300 hover:border-gray-300'}`}
                  placeholder="Enter your School ID"
                />
                {errors.schoolId && <p className="text-red-500 text-sm mt-2 animate-fade-in">{errors.schoolId}</p>}
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    value={loginData.password}
                    onChange={handleInputChange}
                    className={`w-full px-4 py-4 pr-12 border-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all duration-300 ${errors.password ? 'border-red-300 bg-red-50 focus:border-red-400 animate-shake' : 'border-gray-200 focus:border-indigo-300 hover:border-gray-300'}`}
                    placeholder="Enter your password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors duration-200"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
                {errors.password && <p className="text-red-500 text-sm mt-2 animate-fade-in">{errors.password}</p>}
              </div>

              <div className="flex items-center justify-between pt-2">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    name="rememberMe"
                    checked={loginData.rememberMe}
                    onChange={handleInputChange}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded transition-all duration-200"
                  />
                  <label className="ml-3 block text-sm text-gray-700 font-medium">
                    Remember me
                  </label>
                </div>
                <button 
                  onClick={goToForgotPassword}
                  className="text-sm text-indigo-600 hover:text-indigo-800 font-medium transition-colors duration-200 hover:underline"
                >
                  Forgot password?
                </button>
              </div>

              <button
                onClick={handleLogin}
                className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-xl font-bold text-lg hover:from-indigo-700 hover:to-purple-700 transition-all duration-200 flex items-center justify-center gap-3 shadow-xl hover:shadow-2xl transform hover:-translate-y-1 animate-pulse-button"
              >
                <LogIn className="h-6 w-6" />
                Sign In to Dashboard
              </button>
            </div>

            {/* Enhanced Demo Credentials */}
            <div className="mt-8 p-4 sm:p-6 bg-gradient-to-r from-gray-50 to-blue-50 rounded-2xl border border-gray-200">
              <p className="text-sm font-bold text-gray-700 mb-4 text-center">Demo Credentials for Testing</p>
              <div className="space-y-3">
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-200">
                  <p className="text-xs text-gray-600 mb-1"><strong>School:</strong> St. Mary's Elementary</p>
                  <p className="text-xs text-gray-600 mb-1"><strong>School ID:</strong> <code className="bg-blue-100 px-2 py-1 rounded text-blue-800 font-mono">SCH_NYC_STMARY_001</code></p>
                  <p className="text-xs text-gray-600"><strong>Password:</strong> <code className="bg-green-100 px-2 py-1 rounded text-green-800 font-mono">password123</code></p>
                </div>
                <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-200">
                  <p className="text-xs text-gray-600 mb-1"><strong>School:</strong> Riverside High School</p>
                  <p className="text-xs text-gray-600 mb-1"><strong>School ID:</strong> <code className="bg-blue-100 px-2 py-1 rounded text-blue-800 font-mono">SCH_BOS_RIVER_002</code></p>
                  <p className="text-xs text-gray-600"><strong>Password:</strong> <code className="bg-green-100 px-2 py-1 rounded text-green-800 font-mono">password123</code></p>
                </div>
              </div>
            </div>

            {/* Enhanced Security Notice */}
            <div className="mt-6 flex items-start gap-3 p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-200">
              <Shield className="h-6 w-6 text-blue-600 mt-1 flex-shrink-0 animate-pulse" />
              <div>
                <p className="text-sm font-bold text-blue-800">Enterprise Security</p>
                <p className="text-xs text-blue-600 mt-2 leading-relaxed">
                  Your school data is protected with enterprise-grade security. Each school has completely 
                  isolated access to their own information with multi-layered data protection.
                </p>
                <div className="flex flex-wrap gap-2 mt-3">
                  <span className="text-xs bg-blue-200 text-blue-800 px-2 py-1 rounded-full">256-bit SSL</span>
                  <span className="text-xs bg-green-200 text-green-800 px-2 py-1 rounded-full">FERPA Compliant</span>
                  <span className="text-xs bg-purple-200 text-purple-800 px-2 py-1 rounded-full">SOC 2 Certified</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Custom CSS Animations */}
      <style jsx>{`
        @keyframes gradient-x {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes fade-in-up {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes scale-in {
          from { opacity: 0; transform: scale(0.9); }
          to { opacity: 1; transform: scale(1); }
        }
        
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
        
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-5px); }
          75% { transform: translateX(5px); }
        }
        
        @keyframes text-shimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
        
        @keyframes pulse-slow {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.8; }
        }
        
        @keyframes bounce-slow {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-5px); }
        }
        
        .animate-gradient-x {
          background-size: 200% 200%;
          animation: gradient-x 15s ease infinite;
        }
        
        .animate-fade-in {
          animation: fade-in 0.6s ease-out;
        }
        
        .animate-fade-in-up {
          animation: fade-in-up 0.8s ease-out;
        }
        
        .animate-scale-in {
          animation: scale-in 0.5s ease-out;
        }
        
        .animate-float {
          animation: float 3s ease-in-out infinite;
        }
        
        .animate-shake {
          animation: shake 0.5s ease-in-out;
        }
        
        .animate-text-shimmer {
          background: linear-gradient(90deg, #4F46E5, #7C3AED, #4F46E5);
          background-size: 200% auto;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: text-shimmer 3s linear infinite;
        }
        
        .animate-pulse-slow {
          animation: pulse-slow 3s ease-in-out infinite;
        }
        
        .animate-bounce-slow {
          animation: bounce-slow 2s ease-in-out infinite;
        }
        
        .animate-pulse-button {
          box-shadow: 0 0 0 0 rgba(79, 70, 229, 0.4);
          animation: pulse-button 2s infinite;
        }
        
        @keyframes pulse-button {
          0% { box-shadow: 0 0 0 0 rgba(79, 70, 229, 0.4); }
          70% { box-shadow: 0 0 0 10px rgba(79, 70, 229, 0); }
          100% { box-shadow: 0 0 0 0 rgba(79, 70, 229, 0); }
        }
        
        @media (max-width: 640px) {
          .animate-fade-in-up {
            animation-duration: 0.6s;
          }
        }
      `}</style>
    </div>
  );
};

export default SchoolLoginDashboard;
