import type { TeamMember } from "../types";

interface TeamVerificationProps {
  team: TeamMember[];
}

export default function TeamVerification({ team }: TeamVerificationProps) {
  if (team.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">No team data available.</p>
    );
  }

  return (
    <div className="space-y-2">
      {team.map((member, i) => (
        <div
          key={i}
          className="flex items-start justify-between rounded-lg border border-gray-100 bg-gray-50 px-3 py-2"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-800">
                {member.name}
              </span>
              {member.verified ? (
                <span className="rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-700">
                  ✓ verified
                </span>
              ) : (
                <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-600">
                  unverified
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500">{member.role}</p>
            {(member.previous_projects?.length ?? 0) > 0 && (
              <p className="text-xs text-gray-400">
                prev: {member.previous_projects.slice(0, 3).join(", ")}
              </p>
            )}
          </div>
          <div className="ml-2 flex shrink-0 flex-col items-end gap-1">
            {member.linkedin_url && (
              <a
                href={member.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-500 underline"
              >
                LinkedIn
              </a>
            )}
            {member.twitter_url && (
              <a
                href={member.twitter_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-500 underline"
              >
                Twitter
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
