import React, { useState } from 'react';
import { Badge } from './badge';
import { X } from 'lucide-react';

interface TagInputProps {
  placeholder?: string;
  tags: string[];
  onChange: (tags: string[]) => void;
  disabled?: boolean;
}

export function TagInput({ placeholder, tags, onChange, disabled }: TagInputProps) {
  const [inputValue, setInputValue] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;

    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  };

  const addTag = () => {
    const newTag = inputValue.trim();
    if (newTag && !tags.includes(newTag)) {
      onChange([...tags, newTag]);
    }
    setInputValue('');
  };

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index));
  };

  return (
    <div className={`flex flex-wrap gap-2 p-1.5 border rounded-md focus-within:ring-1 focus-within:ring-ring bg-background min-h-[40px] items-center ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
      {tags.map((tag, index) => (
        <Badge key={index} variant="secondary" className="flex items-center gap-1 py-0.5 px-2 h-7">
          {tag}
          <button type="button" onClick={() => removeTag(index)} className="hover:text-destructive transition-colors" disabled={disabled}>
            <X size={12} />
          </button>
        </Badge>
      ))}
      <input
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addTag}
        placeholder={tags.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[80px] bg-transparent outline-none text-sm h-7 px-1"
        disabled={disabled}
      />
    </div>
  );
}
