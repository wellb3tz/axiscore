import React, { useState, useEffect } from 'react';
import io from 'socket.io-client';
import BackButton from './BackButton';
import { useChat } from '../contexts/ChatContext';
import '../styles/western-theme.css';

const socket = io('https://thequickandthedead.onrender.com');

const Chat = () => {
  const [message, setMessage] = useState('');
  const [username, setUsername] = useState('');
  const { messages, addMessage } = useChat();

  useEffect(() => {
    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      setUsername(storedUsername);
    }

    socket.on('message', (msg) => {
      addMessage(msg);
    });

    return () => {
      socket.off('message');
    };
  }, [addMessage]);

  const sendMessage = () => {
    if (message.trim()) {
      const msg = { username, text: message };
      socket.emit('message', msg);
      setMessage(''); // Clear the input field
    }
  };

  return (
    <div className="container">
      <BackButton />
      <h2>Chat</h2>
      <div className="chat-messages">
        {messages.map((msg, index) => (
          <div key={index}>
            <strong>{msg.username}: </strong>{msg.text}
          </div>
        ))}
      </div>
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Type a message"
      />
      <button onClick={sendMessage}>Send</button>
    </div>
  );
};

export default Chat;