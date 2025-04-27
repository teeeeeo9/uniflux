import React, { useState } from 'react';
import './Subscription.css';

const Subscription = () => {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState('');

  const validateEmail = (email) => {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  };

  const handleSubscribe = async () => {
    // Reset any previous error
    setError('');
    
    // Validate email
    if (!email.trim()) {
      setError('Please enter an email address');
      return;
    }
    
    if (!validateEmail(email)) {
      setError('Please enter a valid email address');
      return;
    }
    
    try {
      // This is where you would typically make an API call to save the email
      // For this example, we'll just log the email and simulate success
      console.log('Subscribing email:', email);
      
      // Store email in localStorage for demonstration
      const subscribers = JSON.parse(localStorage.getItem('subscribers') || '[]');
      subscribers.push({
        email: email,
        timestamp: new Date().toISOString()
      });
      localStorage.setItem('subscribers', JSON.stringify(subscribers));
      
      // Show success message
      setSubscribed(true);
      
      // Clear form
      setEmail('');
      
      // Reset after 3 seconds
      setTimeout(() => {
        setSubscribed(false);
      }, 3000);
    } catch (err) {
      console.error('Subscription error:', err);
      setError('Failed to subscribe. Please try again later.');
    }
  };

  return (
    <div className="subscription-container">
      {subscribed ? (
        <div className="subscription-success">
          <span className="success-icon">✓</span>
          <p>Thank you for subscribing!</p>
          <p className="success-message">We'll keep you updated on new features and improvements.</p>
        </div>
      ) : (
        <>
          <div className="subscription-header">
            <h3>Stay Updated</h3>
            <p>Subscribe to receive updates about new features and news sources.</p>
          </div>
          
          <div className="subscription-form">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Your email address"
              className={error ? 'input-error' : ''}
            />
            
            <button 
              className="subscribe-button"
              onClick={handleSubscribe}
            >
              Subscribe
            </button>
          </div>
          
          {error && <p className="error-message">{error}</p>}
        </>
      )}
    </div>
  );
};

export default Subscription; 