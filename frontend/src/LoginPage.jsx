import React, { useState } from 'react';
import { apiService } from "./api";

const LoginPage = ({ onLogin }) => {
  const [userid, setUserid] = useState('');
  const [role, setRole] = useState('student');
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!userid.trim() || !password.trim()) {
      setError('Please enter both user ID and password');
      return;
    }
    
    setIsLoading(true);
    setError('');
    
    try {
      const result = await apiService.login(userid.trim(), password.trim());
      if (onLogin) {
        onLogin(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit();
    }
  };

  const styles = {
    container: {
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 50%, #f0e6ff 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    },
    card: {
      background: 'rgba(255, 255, 255, 0.9)',
      borderRadius: '24px',
      padding: '40px',
      width: '100%',
      maxWidth: '400px',
      boxShadow: '0 20px 40px rgba(0, 0, 0, 0.1)',
      border: '1px solid rgba(255, 255, 255, 0.2)',
      position: 'relative'
    },
    header: {
      textAlign: 'center',
      marginBottom: '32px'
    },
    iconContainer: {
      width: '80px',
      height: '80px',
      background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 16px',
      boxShadow: '0 8px 16px rgba(0, 0, 0, 0.2)',
      position: 'relative'
    },
    icon: {
      width: '40px',
      height: '40px',
      color: 'white'
    },
    statusDot: {
      position: 'absolute',
      top: '-8px',
      right: '-8px',
      width: '24px',
      height: '24px',
      background: '#10b981',
      borderRadius: '50%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
    },
    innerDot: {
      width: '8px',
      height: '8px',
      background: 'white',
      borderRadius: '50%'
    },
    title: {
      fontSize: '32px',
      fontWeight: 'bold',
      background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
      WebkitBackgroundClip: 'text',
      WebkitTextFillColor: 'transparent',
      marginBottom: '8px'
    },
    subtitle: {
      color: '#6b7280',
      fontSize: '18px'
    },
    form: {
      display: 'flex',
      flexDirection: 'column',
      gap: '24px'
    },
    inputGroup: {
      display: 'flex',
      flexDirection: 'column'
    },
    label: {
      fontSize: '14px',
      fontWeight: '600',
      color: '#374151',
      marginBottom: '12px'
    },
    inputContainer: {
      position: 'relative'
    },
    input: {
      width: '100%',
      padding: '16px 16px 16px 48px',
      border: '1px solid #d1d5db',
      borderRadius: '12px',
      fontSize: '16px',
      transition: 'all 0.2s',
      background: 'rgba(249, 250, 251, 0.5)',
      boxSizing: 'border-box'
    },
    inputIcon: {
      position: 'absolute',
      left: '16px',
      top: '50%',
      transform: 'translateY(-50%)',
      width: '20px',
      height: '20px',
      color: '#9ca3af'
    },
    passwordToggle: {
      position: 'absolute',
      right: '16px',
      top: '50%',
      transform: 'translateY(-50%)',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      color: '#6b7280',
      padding: '4px'
    },
    select: {
      width: '100%',
      padding: '16px',
      border: '1px solid #d1d5db',
      borderRadius: '12px',
      fontSize: '16px',
      background: 'rgba(249, 250, 251, 0.5)',
      cursor: 'pointer',
      boxSizing: 'border-box'
    },
    button: {
      width: '100%',
      padding: '16px',
      background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
      color: 'white',
      border: 'none',
      borderRadius: '12px',
      fontSize: '16px',
      fontWeight: '600',
      cursor: 'pointer',
      transition: 'all 0.2s',
      boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)'
    },
    buttonDisabled: {
      opacity: '0.5',
      cursor: 'not-allowed'
    },
    error: {
      background: '#fef2f2',
      border: '1px solid #fecaca',
      color: '#dc2626',
      padding: '12px',
      borderRadius: '8px',
      fontSize: '14px',
      marginBottom: '16px'
    },
    demoBox: {
      background: '#eff6ff',
      borderRadius: '12px',
      padding: '16px',
      marginTop: '24px'
    },
    demoTitle: {
      fontSize: '14px',
      fontWeight: '600',
      color: '#1e40af',
      marginBottom: '8px'
    },
    demoText: {
      fontSize: '12px',
      color: '#3730a3',
      lineHeight: '1.4'
    },
    loadingSpinner: {
      width: '20px',
      height: '20px',
      border: '2px solid white',
      borderTop: '2px solid transparent',
      borderRadius: '50%',
      animation: 'spin 1s linear infinite',
      marginRight: '12px'
    }
  };

  // Simple icons using SVG
  const BotIcon = () => (
    <svg style={styles.icon} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C13.1 2 14 2.9 14 4C14 5.1 13.1 6 12 6C10.9 6 10 5.1 10 4C10 2.9 10.9 2 12 2ZM21 9V7L12 2L3 7V9C3 10.1 3.9 11 5 11V17C5 18.1 5.9 19 7 19H17C18.1 19 19 18.1 19 17V11C20.1 11 21 10.1 21 9ZM11 17H7V11H11V17ZM17 17H13V11H17V17Z"/>
    </svg>
  );

  const UserIcon = () => (
    <svg style={styles.inputIcon} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 12C14.21 12 16 10.21 16 8C16 5.79 14.21 4 12 4C9.79 4 8 5.79 8 8C8 10.21 9.79 12 12 12ZM12 14C9.33 14 4 15.34 4 18V20H20V18C20 15.34 14.67 14 12 14Z"/>
    </svg>
  );

  const ShieldIcon = () => (
    <svg style={styles.inputIcon} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,1L3,5V11C3,16.55 6.84,21.74 12,23C17.16,21.74 21,16.55 21,11V5L12,1M12,7C13.4,7 14.8,8.6 14.8,10V11H16.2V16H7.8V11H9.2V10C9.2,8.6 10.6,7 12,7M12,8.2C11.2,8.2 10.4,8.7 10.4,10V11H13.6V10C13.6,8.7 12.8,8.2 12,8.2Z"/>
    </svg>
  );

  const EyeIcon = () => (
    <svg style={{width: '20px', height: '20px'}} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z"/>
    </svg>
  );

  const EyeOffIcon = () => (
    <svg style={{width: '20px', height: '20px'}} viewBox="0 0 24 24" fill="currentColor">
      <path d="M11.83,9L15,12.16C15,12.11 15,12.05 15,12A3,3 0 0,0 12,9C11.94,9 11.89,9 11.83,9M7.53,9.8L9.08,11.35C9.03,11.56 9,11.77 9,12A3,3 0 0,0 12,15C12.22,15 12.44,14.97 12.65,14.92L14.2,16.47C13.53,16.8 12.79,17 12,17A5,5 0 0,1 7,12C7,11.21 7.2,10.47 7.53,9.8M2,4.27L4.28,6.55L4.73,7C3.08,8.3 1.78,10 1,12C2.73,16.39 7,19.5 12,19.5C13.55,19.5 15.03,19.2 16.38,18.66L16.81,19.09L19.73,22L21,20.73L3.27,3M12,7A5,5 0 0,1 17,12C17,12.64 16.87,13.26 16.64,13.82L19.57,16.75C21.07,15.5 22.27,13.86 23,12C21.27,7.61 17,4.5 12,4.5C10.6,4.5 9.26,4.75 8,5.2L10.17,7.35C10.76,7.13 11.38,7 12,7Z"/>
    </svg>
  );

  return (
    <div style={styles.container}>
      <style>
        {`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          
          .input-focus:focus {
            outline: none !important;
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
          }
          
          .button-hover:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
          }
          
          .select-focus:focus {
            outline: none !important;
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
          }
        `}
      </style>
      
      <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.iconContainer}>
            <BotIcon />
            <div style={styles.statusDot}>
              <div style={styles.innerDot}></div>
            </div>
          </div>
          <h1 style={styles.title}>EduAi</h1>
          <p style={styles.subtitle}>Welcome back! Please sign in to continue</p>
        </div>

        <div style={styles.form}>
          {error && (
            <div style={styles.error}>
              {error}
            </div>
          )}
          
          <div style={styles.inputGroup}>
            <label style={styles.label}>User ID</label>
            <div style={styles.inputContainer}>
              <input
                type="text"
                value={userid}
                onChange={(e) => setUserid(e.target.value)}
                onKeyPress={handleKeyPress}
                style={styles.input}
                className="input-focus"
                placeholder="Enter your user ID"
                disabled={isLoading}
              />
              <UserIcon />
            </div>
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <div style={styles.inputContainer}>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyPress={handleKeyPress}
                style={{...styles.input, paddingRight: '48px'}}
                className="input-focus"
                placeholder="Enter your password"
                disabled={isLoading}
              />
              <ShieldIcon />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={styles.passwordToggle}
                disabled={isLoading}
              >
                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
              </button>
            </div>
          </div>

          <button
            onClick={handleSubmit}
            disabled={isLoading || !userid.trim() || !password.trim()}
            style={{
              ...styles.button,
              ...(isLoading || !userid.trim() || !password.trim() ? styles.buttonDisabled : {})
            }}
            className="button-hover"
          >
            {isLoading ? (
              <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                <div style={styles.loadingSpinner}></div>
                Signing in...
              </div>
            ) : (
              'Sign In'
            )}
          </button>
        </div>

        <div style={styles.demoBox}>
          <div style={styles.demoTitle}>Demo Credentials</div>
          <div style={styles.demoText}>
            Admin: userid="admin", password="admin"<br/>
            Student: userid="student123", password="student123"<br/>
            (For students, userid must match password)
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;