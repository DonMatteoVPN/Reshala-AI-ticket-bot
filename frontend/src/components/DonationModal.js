import React, { useState, useEffect } from 'react';
import { X, Copy, Check, Heart, ExternalLink } from 'lucide-react';

export default function DonationModal({ onClose }) {
    const [config, setConfig] = useState(null);
    const [copied, setCopied] = useState(null);

    useEffect(() => {
        fetch('/donation.config.json')
            .then(r => r.json())
            .then(setConfig)
            .catch(err => console.error('Failed to load donation config:', err));
    }, []);

    const copyAddress = (address) => {
        navigator.clipboard.writeText(address);
        setCopied(address);
        setTimeout(() => setCopied(null), 2000);
    };

    if (!config) {
        return (
            <div className="modal-overlay" onClick={onClose}>
                <div className="modal" onClick={e => e.stopPropagation()}>
                    <div className="loading-spinner" />
                </div>
            </div>
        );
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal donation-modal" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3 className="modal-title">
                        <Heart size={20} style={{ color: 'var(--accent)' }} />
                        Поддержать проект
                    </h3>
                    <button className="btn-icon btn-secondary" onClick={onClose}>
                        <X size={16} />
                    </button>
                </div>

                <div className="donation-content">
                    {/* Трибут Telegram */}
                    {config.telegram_tribute?.enabled && (
                        <a
                            href={config.telegram_tribute.link}
                            className="donation-option donation-tribute"
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <div className="donation-option-icon">
                                <Heart size={20} />
                            </div>
                            <div className="donation-option-info">
                                <div className="donation-option-title">Трибут Telegram</div>
                                <div className="donation-option-subtitle">
                                    @{config.telegram_tribute.username}
                                </div>
                            </div>
                            <ExternalLink size={16} className="donation-option-arrow" />
                        </a>
                    )}

                    {/* Криптовалюта */}
                    {config.crypto?.enabled && config.crypto.wallets.length > 0 && (
                        <>
                            <div className="donation-divider">
                                <span>или криптовалюта</span>
                            </div>

                            {config.crypto.wallets.map((wallet, idx) => (
                                <div key={idx} className="donation-option donation-crypto">
                                    <div className="donation-option-info">
                                        <div className="donation-option-title">{wallet.currency}</div>
                                        <div className="donation-option-subtitle">{wallet.network}</div>
                                    </div>
                                    <div className="wallet-address">
                                        <code>{wallet.address}</code>
                                        <button
                                            className="btn-icon btn-secondary"
                                            onClick={() => copyAddress(wallet.address)}
                                            title="Копировать адрес"
                                        >
                                            {copied === wallet.address ? (
                                                <Check size={14} style={{ color: 'var(--success)' }} />
                                            ) : (
                                                <Copy size={14} />
                                            )}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </>
                    )}
                </div>

                <div className="donation-footer">
                    <p className="text-muted">
                        Спасибо за поддержку! 💚
                    </p>
                </div>
            </div>
        </div>
    );
}
