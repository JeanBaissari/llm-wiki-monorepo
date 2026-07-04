import { detectCommunities } from "../dist/louvain.js";

const nodes = [
  { id: "a", label: "A", linkCount: 2 },
  { id: "b", label: "B", linkCount: 2 },
  { id: "c", label: "C", linkCount: 3 },
  { id: "d", label: "D", linkCount: 3 },
  { id: "e", label: "E", linkCount: 2 },
  { id: "f", label: "F", linkCount: 2 },
];
const edges = [
  { source: "a", target: "b", weight: 10 },
  { source: "b", target: "c", weight: 10 },
  { source: "a", target: "c", weight: 8 },
  { source: "d", target: "e", weight: 10 },
  { source: "e", target: "f", weight: 10 },
  { source: "d", target: "f", weight: 8 },
  { source: "c", target: "d", weight: 1 },
];

const result = detectCommunities(nodes, edges);
console.log(JSON.stringify({
  assignments: [...result.assignments],
  communities: result.communities,
}));
