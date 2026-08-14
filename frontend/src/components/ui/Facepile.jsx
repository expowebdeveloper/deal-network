import Avatar from './Avatar'

/** Overlapping row of small avatars. `people` is [{ initials, color }]. */
export default function Facepile({ people }) {
  return (
    <div className="facepile">
      {people.map((p) => (
        <Avatar key={p.initials} initials={p.initials} color={p.color} size="sm" />
      ))}
    </div>
  )
}
