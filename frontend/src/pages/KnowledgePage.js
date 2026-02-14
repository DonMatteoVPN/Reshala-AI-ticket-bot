import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, Edit3, BookOpen, Save, X, Search, Tag, FileText } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function ArticleModal({ article, onClose, onSave }) {
  const [title, setTitle] = useState(article?.title || '');
  const [content, setContent] = useState(article?.content || '');
  const [category, setCategory] = useState(article?.category || 'general');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!title.trim() || !content.trim()) return;
    setSaving(true);
    try {
      const url = article?.id
        ? `${API}/api/knowledge/${article.id}`
        : `${API}/api/knowledge`;
      const method = article?.id ? 'PUT' : 'POST';
      await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title.trim(), content: content.trim(), category: category.trim() })
      });
      onSave();
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <span className="modal-title" style={{ marginBottom: 0 }}>
            {article?.id ? 'Редактировать статью' : 'Новая статья'}
          </span>
          <button className="btn btn-icon btn-secondary" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="input-group">
          <label className="input-label">Заголовок</label>
          <input
            className="input"
            placeholder="Название статьи..."
            value={title}
            onChange={e => setTitle(e.target.value)}
            data-testid="article-title-input"
          />
        </div>

        <div className="input-group">
          <label className="input-label">Категория</label>
          <input
            className="input"
            placeholder="general, faq, tutorial..."
            value={category}
            onChange={e => setCategory(e.target.value)}
            data-testid="article-category-input"
          />
        </div>

        <div className="input-group">
          <label className="input-label">Содержание</label>
          <textarea
            className="input"
            rows={8}
            placeholder="Содержание статьи. AI будет использовать эту информацию для ответов..."
            value={content}
            onChange={e => setContent(e.target.value)}
            style={{ resize: 'vertical', minHeight: 120 }}
            data-testid="article-content-input"
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving || !title.trim() || !content.trim()}
          style={{ width: '100%' }}
          data-testid="article-save-btn"
        >
          {saving ? 'Сохранение...' : <><Save size={14} /> Сохранить</>}
        </button>
      </div>
    </div>
  );
}

export default function KnowledgePage() {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editArticle, setEditArticle] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  const fetchArticles = useCallback(async () => {
    try {
      const url = searchQuery.trim()
        ? `${API}/api/knowledge/search/${encodeURIComponent(searchQuery.trim())}`
        : `${API}/api/knowledge`;
      const r = await fetch(url);
      const data = await r.json();
      setArticles(data.articles || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    fetchArticles();
  }, [fetchArticles]);

  const deleteArticle = async (id) => {
    await fetch(`${API}/api/knowledge/${id}`, { method: 'DELETE' });
    fetchArticles();
  };

  const openNew = () => { setEditArticle(null); setShowModal(true); };
  const openEdit = (a) => { setEditArticle(a); setShowModal(true); };

  const categories = [...new Set(articles.map(a => a.category || 'general'))];

  return (
    <div data-testid="knowledge-page">
      <div className="card" style={{ marginBottom: 14 }}>
        <div className="card-header">
          <span className="card-title">База знаний AI</span>
          <span className="badge badge-info">{articles.length} статей</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', lineHeight: 1.55 }}>
          Добавляйте статьи для обучения AI. Бот будет использовать эту информацию при ответах пользователям.
        </p>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <div className="search-input-wrap" style={{ flex: 1 }}>
          <Search />
          <input
            className="search-input"
            placeholder="Поиск по статьям..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            data-testid="kb-search-input"
          />
        </div>
        <button className="btn btn-primary" onClick={openNew} data-testid="kb-add-btn">
          <Plus size={16} /> Добавить
        </button>
      </div>

      {categories.length > 1 && (
        <div className="tabs" style={{ marginBottom: 10 }}>
          {categories.map(c => (
            <span key={c} className="badge badge-muted" style={{ cursor: 'default' }}>
              <Tag size={10} /> {c}
            </span>
          ))}
        </div>
      )}

      {loading ? (
        <div className="empty-state"><div className="loading-spinner" /></div>
      ) : articles.length === 0 ? (
        <div className="empty-state" data-testid="kb-empty">
          <div className="empty-icon"><BookOpen size={22} /></div>
          <div className="empty-title">База знаний пуста</div>
          <div className="empty-text">Добавьте статьи, FAQ и инструкции для AI ассистента</div>
        </div>
      ) : (
        articles.map(a => (
          <div
            key={a.id}
            className="kb-article"
            onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
            data-testid={`kb-article-${a.id}`}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="kb-article-title">
                  <FileText size={14} style={{ verticalAlign: -2, marginRight: 5, color: 'var(--accent)' }} />
                  {a.title}
                </div>
                <div className="kb-article-content" style={{
                  WebkitLineClamp: expandedId === a.id ? 'unset' : 3,
                  maxHeight: expandedId === a.id ? 'none' : '60px'
                }}>
                  {a.content}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 4, flexShrink: 0, marginLeft: 8 }}>
                <button
                  className="btn btn-icon btn-secondary"
                  style={{ width: 30, height: 30 }}
                  onClick={e => { e.stopPropagation(); openEdit(a); }}
                  data-testid={`kb-edit-${a.id}`}
                >
                  <Edit3 size={12} />
                </button>
                <button
                  className="btn btn-icon btn-danger"
                  style={{ width: 30, height: 30 }}
                  onClick={e => { e.stopPropagation(); deleteArticle(a.id); }}
                  data-testid={`kb-delete-${a.id}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
            <div className="kb-article-meta">
              <span className="badge badge-muted"><Tag size={9} /> {a.category || 'general'}</span>
              {a.updated_at && (
                <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>
                  {new Date(a.updated_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
            </div>
          </div>
        ))
      )}

      {showModal && (
        <ArticleModal
          article={editArticle}
          onClose={() => setShowModal(false)}
          onSave={fetchArticles}
        />
      )}
    </div>
  );
}
