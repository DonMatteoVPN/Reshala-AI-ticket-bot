import React, { useState } from 'react';
import { AlertTriangle, X, Check } from 'lucide-react';

export default function ConfirmModal({ isOpen, title, message, confirmText = 'Подтвердить', cancelText = 'Отмена', onConfirm, onCancel, danger = false }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onCancel} data-testid="confirm-modal">
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <div style={{
            width: 42,
            height: 42,
            borderRadius: 12,
            background: danger ? 'var(--danger-bg)' : 'var(--warning-bg)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0
          }}>
            <AlertTriangle size={20} color={danger ? 'var(--danger)' : 'var(--warning)'} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>{title}</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 2 }}>{message}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onCancel} data-testid="confirm-cancel">
            <X size={14} /> {cancelText}
          </button>
          <button className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`} onClick={onConfirm} data-testid="confirm-ok">
            <Check size={14} /> {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}
