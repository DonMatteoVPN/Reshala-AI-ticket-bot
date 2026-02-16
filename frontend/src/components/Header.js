import React, { useState } from 'react';
import { Heart } from 'lucide-react';
import DonationModal from './DonationModal';

const LOGO_URL = "https://customer-assets.emergentagent.com/job_reshala-support/artifacts/hsrp3ao6_photo_2026-02-15%2002.01.49.jpeg";

export default function Header({ settings }) {
  const [showDonation, setShowDonation] = useState(false);

  return (
    <header className="header" data-testid="app-header">
      <div className="header-brand">
        <img
          src={LOGO_URL}
          alt="Logo"
          className="header-logo-img"
          style={{
            width: 42,
            height: 42,
            borderRadius: 10,
            objectFit: 'cover',
            boxShadow: '0 0 20px rgba(0, 220, 200, 0.2)',
          }}
        />
        <div>
          <h1><span className="brand-accent">Решала</span> Support</h1>
          <p className="header-subtitle">от DonMatteo</p>
        </div>

        {/* Кнопка доната */}
        <button
          className="donation-btn"
          onClick={() => setShowDonation(true)}
          title="Поддержать проект"
        >
          <Heart size={18} />
        </button>
      </div>

      {/* Модальное окно доната */}
      {showDonation && (
        <DonationModal onClose={() => setShowDonation(false)} />
      )}
    </header>
  );
}
