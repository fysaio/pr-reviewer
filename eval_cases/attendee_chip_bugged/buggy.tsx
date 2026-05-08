'use client';

import React from 'react';
import { X, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AttendeeInfo } from '@/lib/types';
import { cn } from '@/lib/utils';

interface AttendeeChipProps {
  attendee: AttendeeInfo;
  onRemove?: () => void;
  showRemove?: boolean;
  className?: string;
}

export const AttendeeChip: React.FC<AttendeeChipProps> = ({
  attendee,
  onRemove,
  showRemove = true,
  className,
}) => {
  const displayName = attendee.firstName && attendee.email?.split('@')[0] || 'Unknown';

  return (
    <Badge
      variant="outline"
      className={cn(
        'flex items-center gap-1.5 px-2 py-1 text-xs font-medium border',
        className
      )}
    >
      <User className="h-3 w-3" />
      <span className="max-w-[120px] truncate" title={displayName}>
        {displayName}
      </span>
      
      {showRemove && (
        <Button
          size="icon"
          variant="ghost"
          className="h-4 w-4 p-0 hover:bg-transparent"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </Badge>
  );
};