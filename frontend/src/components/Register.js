import React, { useState, useEffect } from 'react';
import BackButton from './BackButton';
import Spinner from './Spinner';
import '../styles/western-theme.css';

const Register = () => {
  const [telegramId, setTelegramId] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    console.log('Register component mounted');
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      if (user) {
        setTelegramId(user.id);
      } else {
        console.error('Telegram user data is not available');
      }
    } else {
      console.error('Telegram WebApp is not defined');
    }
  }, []);

  const handleRegister = () => {
    setLoading(true);
    console.log('Register button clicked');
    fetch('https://thequickandthedead.onrender.com/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ telegram_id: telegramId, username, password }),
    })
      .then(response => response.json())
      .then(data => {
        setLoading(false);
        if (data.msg === "User registered successfully") {
          setMessage("Registration successful! Please log in.");
        } else {
          setMessage(data.msg);
        }
      })
      .catch(error => {
        setLoading(false);
        console.error('Error:', error);
        setMessage('An error occurred. Please try again.');
      });
  };

  return (
    <div className="container">
      <BackButton />
      <h2>Register</h2>
      {message && <p>{message}</p>}
      {loading ? <Spinner /> : (
        <>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button onClick={handleRegister}>Register</button>
        </>
      )}
    </div>
  );
};

export default Register;