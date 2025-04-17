import React from 'react';
import BackButton from './BackButton';
import '../styles/western-theme.css';

const Looting = () => {
  return (
    <div className="container">
      <BackButton redirectTo="/post-login" />
      <h2 style={{ textAlign: 'center' }}>You found:</h2>
      {/* Add any additional content or logic for displaying found items */}
    </div>
  );
};

export default Looting;