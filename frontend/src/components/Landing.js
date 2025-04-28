import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import './Landing.css';
import logo from '../assets/image.png';
import Subscription from './Subscription';
import Feedback from './Feedback';

const Landing = () => {
  const [activeStep, setActiveStep] = useState(0);
  
  // Cycle through the step animations every 4 seconds
  React.useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
    }, 4000);
    
    return () => clearInterval(interval);
  }, []);

  const steps = [
    {
      title: "Select Sources",
      description: "Choose from curated news sources or add your own to create a personalized news feed.",
      icon: "📰"
    },
    {
      title: "Get Summaries",
      description: "Our AI analyzes and summarizes key information from multiple sources, eliminating redundancy.",
      icon: "📊"
    },
    {
      title: "Gain Insights",
      description: "Receive actionable financial insights based on the news that matters most.",
      icon: "💡"
    },
    {
      title: "Execute",
      description: "Take action and execute directly from the app.",
      icon: "🚀"
    }
  ];

  return (
    <div className="landing-page">
      <header className="landing-header">
        <div className="container">
          <div className="landing-nav">
            <div className="logo-container-landing">
              <img src={logo} alt="Uniflux Logo" className="logo" />
              <h1>Uniflux</h1>
            </div>
            <div className="nav-links">
              <Link to="/app" className="app-link">Open App</Link>
              <a href="https://github.com/teeeeeo9/uniflux" target="_blank" rel="noopener noreferrer" className="github-link">
                <svg height="24" width="24" viewBox="0 0 16 16" fill="currentColor">
                  <path fillRule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
                GitHub
              </a>
            </div>
          </div>
          
          <div className="hero-section">
            <div className="hero-content">
              <h2>
                Stop scrolling
                <span className="line-break">Start seeing</span>
              </h2>
              <div className="hero-cta">
                <Link to="/app" className="primary-button">Try Uniflux Now</Link>
                <button 
                  className="secondary-button"
                  onClick={() => {
                    document.getElementById('subscribe-section').scrollIntoView({ behavior: 'smooth' });
                  }}
                >
                  Subscribe for Updates
                </button>
              </div>
            </div>
            <div className="hero-image">
              {/* Placeholder for a hero image */}
              <div className="image-placeholder">
                <div className="image-animation">
                  <div className="animation-content">
                    <span className="animation-icon">{steps[activeStep].icon}</span>
                    <h3>{steps[activeStep].title}</h3>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="steps-section">
          <div className="container">
            <h2>How Uniflux Works</h2>
            <div className="steps-container">
              {steps.map((step, index) => (
                <div 
                  key={index} 
                  className={`step-card ${activeStep === index ? 'active' : ''}`}
                  onClick={() => setActiveStep(index)}
                >
                  <div className="step-number">{index + 1}</div>
                  <div className="step-icon">{step.icon}</div>
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="benefits-section">
          <div className="container">
            <h2>Why Choose Uniflux</h2>
            <div className="benefits-grid">
              <div className="benefit-card">
                {/* <div className="benefit-icon">⏱️</div> */}
                <h3>Save Time</h3>
                <p>Get the most important news without reading dozens of articles.</p>
              </div>
              <div className="benefit-card">
                {/* <div className="benefit-icon">🔍</div> */}
                <h3>Reduce Noise</h3>
                <p>Filter out redundant information and focus on what matters.</p>
              </div>
              <div className="benefit-card">
                {/* <div className="benefit-icon">💰</div> */}
                <h3>Make Better Decisions</h3>
                <p>Receive actionable insights to guide your financial choices.</p>
              </div>
            </div>
          </div>
        </section>

        <section id="subscribe-section" className="subscribe-section">
          <div className="container">
            <h2>Stay Updated with Uniflux</h2>
            <p>Get notified about new features, sources, and improvements.</p>
            <div className="subscription-wrapper">
              <Subscription />
            </div>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <div className="container">
          <div className="footer-content">
            <div className="footer-logo">
              {/* <img src={logo} alt="Uniflux Logo" className="logo" /> */}
              <span>Uniflux</span>
            </div>
            <div className="footer-links">
              <Link to="/app">Open App</Link>
              <a href="https://github.com/yourusername/uniflux" target="_blank" rel="noopener noreferrer">GitHub</a>
              <button 
                className="contact-link"
                onClick={() => {
                  // This will trigger the Feedback component to open
                  document.querySelector('.feedback-button').click();
                }}
              >
                Contact Us
              </button>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; {new Date().getFullYear()} Uniflux. All rights reserved.</p>
          </div>
        </div>
      </footer>

      {/* Feedback component for contact functionality */}
      <Feedback />
    </div>
  );
};

export default Landing; 