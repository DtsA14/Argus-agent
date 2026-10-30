export default function List({ items }) {
  return <ul>{items.map(i => <li key={i}>{i}</li>)}</ul>
}
