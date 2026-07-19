import { AuditEntry } from '../api/client'

interface Props {
  entries: AuditEntry[]
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function formatValue(val: string | undefined | null) {
  if (val === undefined || val === null || val === '') return '(未設定)'
  // Try to parse as JSON in case Redmine returns structured values.
  try {
    const parsed = JSON.parse(val)
    return typeof parsed === 'object' ? JSON.stringify(parsed) : String(val)
  } catch {
    return String(val)
  }
}

function IconComment() {
  return (
    <span style={{ fontSize: '1.2rem', marginRight: '0.5rem' }}>💬</span>
  )
}

function IconChange() {
  return (
    <span style={{ fontSize: '1.2rem', marginRight: '0.5rem' }}>🔄</span>
  )
}

export function AuditLog({ entries }: Props) {
  if (!entries || entries.length === 0) {
    return (
      <div className="card" style={{ marginTop: '1rem' }}>
        <h3>監査ログ</h3>
        <div className="empty">履歴はありません</div>
      </div>
    )
  }

  // Sort entries by created_on ascending (oldest first).
  const sorted = [...entries].sort((a, b) => {
    return new Date(a.created_on).getTime() - new Date(b.created_on).getTime()
  })

  return (
    <div className="card" style={{ marginTop: '1rem' }}>
      <h3>監査ログ</h3>
      <div style={{ position: 'relative', paddingLeft: '0.5rem' }}>
        {/* Vertical timeline line */}
        <div
          style={{
            position: 'absolute',
            left: '12px',
            top: '40px',
            bottom: '0',
            width: '2px',
            backgroundColor: '#e0e0e0',
            zIndex: 1,
          }}
        />

        {sorted.map((entry, idx) => (
          <div
            key={idx}
            style={{
              position: 'relative',
              paddingLeft: '2rem',
              marginBottom: '1.5rem',
            }}
          >
            {/* Timeline dot */}
            <div
              style={{
                position: 'absolute',
                left: '6px',
                top: '4px',
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                backgroundColor: entry.type === 'comment' ? '#3498db' : '#e67e22',
                border: '2px solid white',
                boxShadow: '0 0 0 1px #ddd',
              }}
            />

            {/* Entry header with author and timestamp */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: '0.3rem',
                fontSize: '0.85rem',
                color: '#666',
              }}
            >
              {entry.type === 'comment' ? <IconComment /> : <IconChange />}
              <strong>{entry.author || 'システム'}</strong>
              <span style={{ marginLeft: '0.5rem' }}>
                {formatDate(entry.created_on)}
              </span>
            </div>

            {/* Comment section */}
            {entry.comment && (
              <div
                style={{
                  backgroundColor: '#f8f9fa',
                  border: '1px solid #e9ecef',
                  borderRadius: '4px',
                  padding: '0.6rem 0.8rem',
                  marginTop: '0.3rem',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {entry.comment}
              </div>
            )}

            {/* Field changes section */}
            {entry.changes.length > 0 && (
              <table
                style={{
                  width: '100%',
                  marginTop: '0.5rem',
                  fontSize: '0.9rem',
                  borderCollapse: 'collapse',
                }}
              >
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '0.2rem 0.5rem 0.2rem 0' }}>
                      フィールド
                    </th>
                    <th style={{ textAlign: 'left', padding: '0.2rem 0.5rem' }}>
                      変更前
                    </th>
                    <th style={{ textAlign: 'left', padding: '0.2rem 0.5rem 0.2rem 0.5rem' }}>
                      変更後
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {entry.changes.map((c, cidx) => (
                    <tr key={cidx}>
                      <td style={{ padding: '0.3rem', fontWeight: 500 }}>
                        {c.display_field || c.field}
                      </td>
                      <td style={{ padding: '0.3rem', color: '#999' }}>
                        {formatValue(c.old_value)}
                      </td>
                      <td style={{ padding: '0.3rem 0.3rem 0.3rem 0.3rem', fontWeight: 500 }}>
                        {formatValue(c.new_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
