import type { Ticket } from "./api/client";

export function groupTicketsByTracker(tickets: Ticket[]) {
  const groups = new Map<
    Ticket["tracker"],
    { tracker: Ticket["tracker"]; name: string; tickets: Ticket[] }
  >();

  for (const ticket of tickets) {
    const group = groups.get(ticket.tracker);
    if (group) {
      group.tickets.push(ticket);
    } else {
      groups.set(ticket.tracker, {
        tracker: ticket.tracker,
        name: ticket.tracker_name,
        tickets: [ticket],
      });
    }
  }

  return [...groups.values()];
}
