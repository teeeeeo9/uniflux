import React, { useState } from 'react';
import './Subscription.css';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

const Subscription = () => {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    
    setIsSubmitting(true);
    
    try {
      // Send subscription to backend
      const response = await fetch(`${API_URL}/subscribe`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({
          email: email,
          source: 'main-subscription'
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to subscribe');
      }
      
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
      setError(err.message || 'Failed to subscribe. Please try again later.');
    } finally {
      setIsSubmitting(false);
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
              disabled={isSubmitting}
            />
            
            <button 
              className={`subscribe-button ${isSubmitting ? 'submitting' : ''}`}
              onClick={handleSubscribe}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Subscribing...' : 'Subscribe'}
            </button>
          </div>
          
          {error && <p className="error-message">{error}</p>}
        </>
      )}
    </div>
  );
};

export default Subscription; 